import io
import logging
import re
import zlib
from typing import (
    BinaryIO, Iterator, Optional, Any, List, Dict, Mapping, cast, Tuple, Union,
    Iterable
)

from minimal_pdf_parser.base import (
    OpenDictToken, CloseDictToken, OpenArrayToken, CloseArrayToken,
    StringObject, NameObject, WordToken, ArrayObject, DictObject, BooleanObject,
    NullObject, IndirectRef, IndirectObject, StreamObject, get_num, get_string,
    check, checked_cast, NumberObject
)
from minimal_pdf_parser.content_parser import ContentParser, Text, SetFont
from minimal_pdf_parser.pdf_encodings import STD_ENCODING, ENCODING_BY_NAME
from minimal_pdf_parser.security import StandardEncrypterFactory, Encrypter
from minimal_pdf_parser.tokenizer import (
    PDFTokenizer, XrefEntry, BinaryStreamWrapper, LINE_FEED, CARRIAGE_RETURN,
    _bytes_to_string, StreamWrapper)

BUF_SIZE = 40  # 96

Encoding = Mapping[int, str]
IndirectOrStreamObject = Union[IndirectObject, StreamObject]
PDFObject = Union[NullObject, IndirectObject, StreamObject, DictObject]


class StreamFactory:
    def create(self, stream: BinaryIO) -> BinaryIO:
        pass


class DeflateStreamWrapper(StreamWrapper):
    def __init__(self, window: Iterable[bytes]):
        StreamWrapper.__init__(self)
        self._it = iter(window)
        self._decompressobj = zlib.decompressobj()
        self._cur = b''
        self._i = 0

    def _get(self) -> int:
        if self._i >= len(self._cur):
            self._cur = b''
            while not self._cur:
                self._cur = self._decompressobj.decompress(next(self._it))
            self._i = 0

        ret = self._cur[self._i]
        self._i += 1
        return ret


class FontParser:
    """
    Table 111 – Entries in a Type 1 font dictionary
    Table 121 – Entries in a Type 0 font dictionary
    """
    _logger = logging.getLogger(__name__)

    def __init__(self, document: "PDFDocument",
                 unicode_by_glyph_name: Mapping[bytes, str],
                 encoding_by_name: Mapping[str, Encoding]):
        self._document = document
        self._unicode_by_glyph_name = unicode_by_glyph_name
        self._encoding_by_name = encoding_by_name
        self._encoding_by_obj_num = cast(Dict[int, Encoding], {})

    def parse(self, v: Any) -> Encoding:
        font_object = checked_cast(DictObject, self._document.get_object(v))
        if isinstance(font_object, IndirectRef):
            obj_num = font_object.obj_num
            try:
                return self._encoding_by_obj_num[obj_num]
            except KeyError:
                font_object = self._document.deref_object(font_object)
                encoding = self._parse_font_object(font_object)
                self._encoding_by_obj_num[obj_num] = encoding
                return encoding
        else:
            return self._parse_font_object(font_object)

    def _parse_font_object(self, font_object: DictObject) -> Encoding:
        subtype = self._get_subtype(font_object)
        if subtype == b"/Type0":
            encoding = self._parse_type0_font(font_object)
        elif subtype == b"/Type1":
            encoding = self._parse_type1_font(font_object)
        elif subtype == b"/TrueType":
            encoding = self._parse_truetype_font(font_object)
        else:
            raise ValueError()
        self._logger.info("Encoding: %s", encoding)
        return encoding

    def _get_subtype(self, obj: DictObject) -> bytes:
        try:
            subtype_object = self._document.get_object(obj[b"/Subtype"])
        except KeyError:
            raise
        else:
            return cast(NameObject, subtype_object).bs

    def _parse_type0_font(self, font_object: DictObject) -> Encoding:
        try:
            encoding_object_or_ref = font_object[b"/Encoding"]
            encoding_object = self._document.get_object(encoding_object_or_ref)
        except KeyError:
            return STD_ENCODING
        else:
            if isinstance(encoding_object, NameObject):
                encoding_name = cast(NameObject, encoding_object).bs
                try:
                    encoding = ENCODING_BY_NAME[encoding_name]
                    return encoding
                except KeyError:
                    try:
                        to_unicode_stream_wrapper = self._document.get_stream(
                            font_object[b"/ToUnicode"])
                        # 9.10.3 ToUnicode CMaps
                        encoding = ContentParser().parse_to_unicode(
                            to_unicode_stream_wrapper)
                        self._logger.info("To Unicode: %s", encoding)
                        return encoding  # TODO apply to base encoding
                    except KeyError:
                        raise
            elif isinstance(encoding_object, DictObject):
                base_encoding = self._get_base1_encoding(encoding_object)
                return self._apply_differences(encoding_object, base_encoding)
            else:
                raise ValueError()

    def _check_type(self, encoding_object: DictObject):
        try:
            type_object = self._document.get_object(encoding_object[b"/Type"])
        except KeyError:
            pass
        else:
            type_name = cast(NameObject, type_object).bs
            assert type_name == b"/Encoding"

    def _parse_type1_font(self, font_object: DictObject) -> Encoding:
        """
        9.6.2 Type 1 Fonts
        """
        try:
            encoding_object = self._document.get_object(
                font_object[b"/Encoding"])
        except KeyError:
            # try with b"/ToUnicode"
            return STD_ENCODING
        else:
            if isinstance(encoding_object, NameObject):
                encoding_name = cast(NameObject, encoding_object).bs
                encoding = ENCODING_BY_NAME.get(encoding_name, [])
                return encoding
            elif isinstance(encoding_object, DictObject):
                base_encoding = self._get_base1_encoding(encoding_object)
                return self._apply_differences(encoding_object, base_encoding)
            else:
                raise ValueError()

    # BaseFont

    def _get_base1_encoding(self, encoding_object) -> Encoding:
        encoding_object = cast(DictObject, encoding_object)
        self._check_type(encoding_object)
        try:
            base_encoding_object = self._document.get_object(
                encoding_object[b"/BaseEncoding"])
        except KeyError:
            base_encoding = STD_ENCODING
        else:
            base_encoding_name = cast(NameObject, base_encoding_object).bs
            base_encoding = ENCODING_BY_NAME.get(base_encoding_name, [])
        return base_encoding

    def _parse_truetype_font(self, font_object: DictObject) -> Encoding:
        """
        9.6.3 TrueType Fonts
        """
        try:
            encoding_object = self._document.get_object(
                font_object[b"/Encoding"])
        except KeyError:
            # try with b"/ToUnicode"
            return STD_ENCODING
        else:
            if isinstance(encoding_object, NameObject):
                encoding_name = cast(NameObject, encoding_object).bs
                encoding = ENCODING_BY_NAME.get(encoding_name, [])
                return encoding
            elif isinstance(encoding_object, DictObject):
                base_encoding = self._get_base1_encoding(encoding_object)
                self._logger.error("TODO enc %s", base_encoding)  # TODO
            else:
                raise ValueError()

    def _apply_differences(self, encoding_object: DictObject,
                           base_encoding: Encoding) -> Encoding:
        try:
            differences = self._document.get_object(
                encoding_object[b"/Differences"])
        except KeyError:
            return base_encoding
        else:
            encoding = dict(base_encoding)
            differences_array = cast(ArrayObject, differences)
            i = 0
            for element in differences_array:
                if isinstance(element, NumberObject):
                    i = element.value
                elif isinstance(element, NameObject):
                    element_name = element.bs
                    encoding[i] = self._unicode_by_glyph_name.get(element_name,
                                                                  '\ufffd')
                    i += 1
                else:
                    raise ValueError()
            return encoding


class PDFDocument:
    """A representation of a PDF document, after reading the xref table."""
    _logger = logging.getLogger(__name__)

    def __init__(self, parser: "PDFParser", doc_id: Optional[ArrayObject],
                 size: int, root: IndirectRef,
                 encrypt: Optional[Any],
                 xref_table: Mapping[int, XrefEntry]):
        self.parser = parser

        self._font_parser = FontParser(self, {}, ENCODING_BY_NAME)
        self.doc_id = doc_id
        self.size = size
        self.root = root
        self.encrypt = encrypt
        self.xref_table = xref_table
        self._obj_by_num = cast(Dict[int, Any], {})
        self._offsets = cast(List[int], [])
        self._encrypter = cast(Optional[Encrypter], None)

    def extract_text(self) -> Iterator[str]:
        if self.encrypt is not None:
            encryption = self.parse_encryption(self.get_object(self.encrypt))
            self._encrypter = encryption.create()
            PDFDocument._logger.debug("Encryption key found %s",
                                      self._encrypter.encryption_key)

        kids = self._get_pages_kids()
        stack = list(kids)
        while stack:
            kid = stack.pop(0)
            kid_object = self.get_object(kid)
            PDFDocument._logger.debug("Examine kid: %s", kid_object)
            try:
                contents = kid_object[b"/Contents"]
            except KeyError:
                kids = kid_object[b"/Kids"]
                stack = list(kids) + stack
            else:
                # kid is a page
                encoding_by_ref = self._handle_fonts(kid_object)
                PDFDocument._logger.debug("Contents: %s",
                                          self.get_object(contents))
                stream_wrapper = self.get_stream(contents)
                cur_encoding = None  # TODO
                self._logger.error("TODO enc %s", cur_encoding)
                # should know the fonts

                encoding = STD_ENCODING
                for x in ContentParser().parse_content(stream_wrapper):
                    if isinstance(x, SetFont):
                        encoding = encoding_by_ref.get(x.name, STD_ENCODING)
                        if not encoding:
                            raise ValueError(repr(encoding_by_ref))
                    elif isinstance(x, Text):
                        try:
                            text = "".join(
                                encoding.get(y, '\ufffd') for y in x.text)
                            yield text
                        except (IndexError, KeyError):
                            self._logger.exception("%s %s", repr(x.text),
                                                   encoding)
                    else:
                        self._logger.debug("Ignore %s", x)

    def get_root_object(self):
        return self.get_object(self.root)

    def get_object(self, obj: Union[IndirectRef, PDFObject]) -> PDFObject:
        """
        Deref the obj if necessary

        :param obj: the obj or a ref.
        :return: the obj
        """
        if isinstance(obj, IndirectRef):
            return self.deref_object(obj)
        else:
            return obj

    def deref_object(self, obj: IndirectRef) -> PDFObject:
        try:
            return self._get_indirect_object(obj).object
        except KeyError:
            return NullObject

    def _handle_fonts(self, kid_object) -> Mapping[bytes, Encoding]:
        encoding_by_ref = {}
        resources = kid_object[b"/Resources"]  # 7.8.3
        for k, v in resources.get(b"/Font", {}).items():
            encoding = self._font_parser.parse(v)
            encoding_by_ref[k] = encoding
        return encoding_by_ref

    def get_stream(self, obj: Any) -> StreamWrapper:
        if isinstance(obj, IndirectRef):
            try:
                stream_obj = self._get_indirect_object(obj)
            except KeyError:
                return BinaryStreamWrapper(io.BytesIO())
        else:
            stream_obj = obj
        checked_cast(StreamObject, stream_obj)
        window = self.parser.stream_window(stream_obj, self._encrypter)
        return DeflateStreamWrapper(window)

    def _get_pages_kids(self):
        root_object = self.get_root_object()
        PDFDocument._logger.debug("Root obj %s", root_object)
        pages_object = self.get_object(root_object[b"/Pages"])
        PDFDocument._logger.debug("Pages obj %s", pages_object)
        kids = checked_cast(ArrayObject,
                            self.get_object(pages_object[b"/Kids"]))
        return kids

    def _get_indirect_object(self, ref: IndirectRef
                             ) -> IndirectOrStreamObject:
        """Convert a ref to an indirect object or a stream object"""
        obj_num = ref.obj_num
        try:
            return self._obj_by_num[obj_num]
        except KeyError:
            byte_offset = int(self.xref_table[obj_num].byte_offset)

            obj = self.read_indirect_object(byte_offset)
            self._obj_by_num[obj_num] = obj
        return obj

    def read_indirect_object(self, byte_offset: int
                             ) -> IndirectOrStreamObject:
        self._offsets.append(self.parser.tell())
        self.parser.seek(byte_offset)
        obj_num, gen_num = map(int, self.parser.read_obj_line())
        # TODO: create tokenizer ? TODO: encrypter
        obj = self.parser.read_object()
        endobj_word = self._read_endobj_word()
        if endobj_word == b"stream":  # open a stream
            start, length = self._read_stream(obj)
            ret = StreamObject(obj_num, gen_num, obj, start, length)
        elif endobj_word == b"endobj":
            ret = IndirectObject(obj_num, gen_num, obj)
        else:
            raise Exception(endobj_word)

        byte_offset = self._offsets.pop()
        self.parser.seek(byte_offset)
        return ret

    def _read_endobj_word(self):
        endobj_word = self.parser.read_endobj_line()
        if not endobj_word:  # sometimes just a void line
            endobj_word = self.parser.read_endobj_line()
        return endobj_word

    def _read_stream(self, obj: Any) -> Tuple[int, int]:
        start = self.parser.tell()
        obj = checked_cast(DictObject, obj)
        length_obj = checked_cast(NumberObject,
                                  self.get_object(obj[b"/Length"]))
        length = length_obj.value
        self.parser.seek(length, io.SEEK_CUR)
        end_stream_word = self.parser.read_endobj_line()
        if not end_stream_word:
            end_stream_word = self.parser.read_endobj_line()
        self.parser.check(end_stream_word == b"endstream",
                          "Expected `endstream`, was {}", end_stream_word)
        endobj_word = self.parser.read_endobj_line()
        self.parser.check(endobj_word == b"endobj", "")
        return start, length

    def parse_encryption(self,
                         encryption: DictObject) -> StandardEncrypterFactory:
        """
        Table 20 – Entries common to all encryption dictionaries
        Table 21 – Additional encryption dictionary entries for the standard
        security handler

        Example:

            8 0 obj            % Encryption dictionary
                <<  /Filter /MySecurityHandlerName
                    /V 4       % Version 4: allow crypt
                    ...
        """
        filter_obj = checked_cast(NameObject, encryption[b"/Filter"])
        check(filter_obj.bs == b"/Standard",
              "Can't decrypt non /Standard filter, was {}", filter_obj.bs)
        version = get_num(encryption, b"/V", 0)
        check(version in (1, 2, 3), "Can't decrypt v {}", version)
        # additional
        revision_num = get_num(encryption, b"/R")
        hashed_owner_and_user_passwd = get_string(encryption, b"/O")
        hashed_user_passwd = get_string(encryption, b"/U")
        permissions = get_num(encryption, b"/P", 0)
        # encrypt_metadata = checked_cast(BooleanObject,
        #                                 encryption[b"EncryptMetadata"]).value

        doc_id = [checked_cast(StringObject, self.get_object(o)).bs for o in
                  checked_cast(ArrayObject, self.doc_id)]

        if version == 1:
            length = 40
            return StandardEncrypterFactory(
                doc_id, version, revision_num, length, permissions,
                hashed_owner_and_user_passwd,
                hashed_user_passwd)
        elif version == 2 or version == 3:
            length = get_num(encryption, b"/Length", 40)
            return StandardEncrypterFactory(
                doc_id, version, revision_num, length, permissions,
                hashed_owner_and_user_passwd,
                hashed_user_passwd)
        elif version == 4:
            # TODO
            cf = encryption[b"/CF"]
            stmf = checked_cast(NameObject, encryption[b"/StmF"]).bs
            strf = checked_cast(NameObject, encryption[b"/StrF"]).bs
            eff = checked_cast(NameObject, encryption[b"/EFF"]).bs
            self._logger.debug("Version 4: %s, %s, %s, %s", cf, stmf, strf, eff)

        raise Exception(str(version))


class PDFParser:
    def __init__(self, stream: BinaryIO):
        self._stream = stream

    def tell(self) -> int:
        return self._stream.tell()

    def seek(self, offset: int, whence: int = io.SEEK_SET):
        self._stream.seek(offset, whence)

    def parse(self):
        return self.parse_document()

    def parse_document(self) -> PDFDocument:
        start_xref = self._find_start_xref()
        xref_table = self.get_xref_table(start_xref)
        # the trailer keyword was read, read the trailer dict now.
        trailer_dict = self.read_dict()
        size = trailer_dict[b"/Size"].value
        root = trailer_dict[b"/Root"]
        try:
            encrypt = trailer_dict[b"/Encrypt"]
        except KeyError:
            encrypt = None
            doc_id = None
        else:
            doc_id = trailer_dict[b"/ID"]

        # look for previous xref tables
        while True:
            try:
                other_start_xref = trailer_dict[b"/Prev"].value
            except KeyError:
                break

            other_xref_table = self.get_xref_table(other_start_xref)
            trailer_dict = self.read_dict()
            for k, v in other_xref_table.items():
                # fill the missing elements
                if k not in xref_table:
                    xref_table[k] = v
        return PDFDocument(self, doc_id, size, root, encrypt, xref_table)

    def get_xref_table(self, start_xref: int) -> Dict[int, XrefEntry]:
        """Read the xref table and the trailer keyword.

        Example:

            xref
            0 1
            0000000000 65535 f
            3 1
            0000025325 00000 n
            23 2
            0000025518 00002 n
            0000025635 00000 n
            30 1
            0000025777 00000 n
        """
        self._stream.seek(start_xref)
        line = self.readline()
        check(line == b"xref", "Can't find `xref` word at offset {}",
              self._stream.tell())
        line = self.readline()
        entry_by_ref_num = {}
        while line and line != b"trailer":
            off, n = map(int, line.split())
            for i in range(off, off + n):
                line = self.readline()
                byte_offset, gen_number, kw = line.split()
                entry_by_ref_num[i] = XrefEntry(byte_offset, gen_number, kw)
            line = self.readline()
        return entry_by_ref_num

    def read_dict(self) -> DictObject:
        return checked_cast(DictObject, self.read_object())

    @staticmethod
    def check(value: bool, format_string: str, *parameters):
        if value:
            return

        raise Exception("Parser" + format_string.format(*parameters))

    def read_object(self):
        tokenizer = PDFTokenizer.create(self._stream)
        return ObjectParser(tokenizer).parse()

    def _find_start_xref(self) -> int:
        """Find the startxref value.

        Example:

            startxref
            18799
            %%EOF
        """
        it = reverse_reader(self._stream)
        expected_eof = next(it)
        while not expected_eof:
            expected_eof = next(it)
        if expected_eof != b"%%EOF":
            raise ValueError(expected_eof)
        startxref = int(next(it))
        if next(it) != b"startxref":
            raise ValueError()
        return startxref

    def skip_eol(self):
        self.readline()

    def take_stream(self, length: int) -> bytes:
        return self._stream.read(length)

    def read_obj_line(self) -> Tuple[bytes, bytes]:
        line = self.readline()
        obj_num, gen_num, obj_word = line.split()
        assert obj_word == b"obj"
        return obj_num, gen_num

    def read_endobj_line(self) -> bytes:
        return self.readline()

    def stream_window(self, stream_obj: StreamObject, encrypter: Encrypter
                      ) -> Iterable[bytes]:
        self._stream.seek(stream_obj.start, io.SEEK_SET)
        if encrypter is None:
            yield from self._stream_window(stream_obj)
        else:
            ec = encrypter.chunks_encrypter(stream_obj.obj_num,
                                            stream_obj.gen_num)
            for c in self._stream_window(stream_obj):
                yield ec.chunk(c)

    def _stream_window(self, stream_obj: StreamObject):
        for i in range(0, stream_obj.length - BUF_SIZE, BUF_SIZE):
            yield self._stream.read(BUF_SIZE)
        yield self._stream.read(stream_obj.length % BUF_SIZE)

    def readline(self):
        cr = False
        cs = []
        while True:
            bytes_read = self._stream.read(1)
            if not bytes_read:
                break
            c = bytes_read[0]
            if c == LINE_FEED:
                break
            if c == CARRIAGE_RETURN:
                cr = True
            elif cr:
                self._stream.seek(-1, io.SEEK_CUR)
                break
            else:
                cs.append(c)

        return _bytes_to_string(cs)


def reverse_reader(stream: BinaryIO) -> Iterator[bytes]:
    stream.seek(0, io.SEEK_END)
    remainders = []
    while True:
        if stream.tell() == 0:
            break

        to_read = min(BUF_SIZE, stream.tell())
        stream.seek(-to_read, io.SEEK_CUR)
        buf = stream.read(to_read)
        stream.seek(-to_read, io.SEEK_CUR)
        lines = re.split(b"(\r|\n|\r\n)", buf)
        if len(lines) == 1:  # no EOL
            remainders.insert(0, lines[0])
        else:
            i = len(lines) - 1
            yield lines[i] + b"".join(remainders)
            i -= 2
            while i > 0:
                yield lines[i]
                i -= 2
            remainders = [lines[i]]

    yield b"".join(remainders)


class ObjectParser:
    """Parser for PDF objects"""

    def __init__(self, tokenizer: PDFTokenizer):
        self._tokenizer = tokenizer
        self._it = iter(self._tokenizer)
        self._cur = []

    def parse(self):
        stack = []
        prev_token = None
        while True:
            if prev_token is None:
                token = next(self._it)
            else:
                token = prev_token
                prev_token = None

            if token is OpenDictToken:
                stack.append([token])
            elif token is CloseDictToken:
                dict_objs = stack.pop()
                assert dict_objs[0] is OpenDictToken
                d = {}
                for i in range(1, len(dict_objs), 2):
                    key = checked_cast(NameObject, dict_objs[i])
                    d[key.bs] = dict_objs[i + 1]
                obj = DictObject(d)
                if stack:
                    stack[-1].append(obj)
                else:
                    return obj

            elif token is OpenArrayToken:
                stack.append([token])
            elif token is CloseArrayToken:
                array_objs = stack.pop()
                assert array_objs[0] is OpenArrayToken, repr(array_objs)
                obj = ArrayObject(array_objs[1:])
                if stack:
                    stack[-1].append(obj)
                else:
                    return obj

            elif isinstance(token, (StringObject, NumberObject, NameObject)):
                if stack:
                    stack[-1].append(token)
                else:
                    return token
            elif isinstance(token, WordToken):
                token = cast(WordToken, token)
                if token.bs == b"true":
                    obj = BooleanObject(True)
                elif token.bs == b"true":
                    obj = BooleanObject(False)
                elif token.bs == b"null":
                    obj = NullObject
                elif token.bs == b"R":
                    gen_num = stack[-1].pop()
                    obj_num = stack[-1].pop()
                    obj = IndirectRef(obj_num, gen_num)
                else:
                    assert False, repr(token)
                if stack:
                    stack[-1].append(obj)
                else:
                    return obj

            else:
                assert False, repr(token)
