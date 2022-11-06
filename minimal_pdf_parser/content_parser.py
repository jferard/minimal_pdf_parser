from typing import NamedTuple, cast, List, Iterator, Union, Any, Mapping

from minimal_pdf_parser.base import (
    NameObject, WordToken, checked_cast, NumberObject, check,
    OpenArrayToken, CloseArrayToken, StringObject, ArrayObject)
from minimal_pdf_parser.tokenizer import (PDFTokenizer, StreamWrapper)


class SetFont:
    def __init__(self, name: bytes, size: int):
        self.name = name
        self.size = size

    def __repr__(self) -> str:
        return "SetFont({}, {})".format(self.name, self.size)


TextMatrix = NamedTuple("TextMatrix", [("matrix", List[List[NumberObject]])])


class Text:
    def __init__(self, text: bytes):
        self.text = text

    def __repr__(self) -> str:
        return "Text({})".format(self.text)


Td = NamedTuple("Td", [("tx", float), ("ty", float)])
TD = NamedTuple("TD", [("tx", float), ("ty", float)])


class ContentParser:
    def parse_content(self, stream_wrapper: StreamWrapper
                      ) -> Iterator[Union[SetFont, Text, TextMatrix, Td]]:
        stack = []

        # See : Table A.1 – PDF content stream operators
        for token in PDFTokenizer(stream_wrapper):
            if isinstance(token, WordToken):
                token_bytes = token.bs
                if token_bytes == b"cm":
                    a, b, c, d, e, f = stack
                    # print("Modify matrix {}".format([[a, b, 0], [c, d, 0], [e, f, 1]]))
                elif token_bytes == b"q":
                    pass
                    # print("Save G perm")
                elif token_bytes == b"Q":
                    pass
                    # print("Restore G perm")
                elif token_bytes == b"BDC":  # marked content
                    stack = []
                elif token_bytes == b"EMC":  # end marked content
                    stack = []
                elif token_bytes == b"BT":  # begin text
                    stack = []
                elif token_bytes == b"ET":  # end text
                    stack = []
                elif token_bytes == b"gs":  # set graphic state
                    stack = []
                elif token_bytes == b"Tc":  # character spacing
                    stack = []
                elif token_bytes == b"Tw":  # word spacing
                    stack = []
                elif token_bytes == b"Tf":  # font
                    font_name_object, size = stack
                    yield SetFont(checked_cast(NameObject, font_name_object).bs,
                                  checked_cast(NumberObject, size).value)
                elif token_bytes == b"Tm":  # text matrix
                    a, b, c, d, e, f = stack
                    yield TextMatrix([[a, b, 0], [c, d, 0], [e, f, 1]])
                elif token_bytes == b"Tj":  # text
                    string_obj, = stack
                    yield Text(string_obj.bs)
                elif token_bytes == b"TJ":
                    array_obj = stack
                    check(array_obj[0] == OpenArrayToken, "")
                    check(array_obj[-1] == CloseArrayToken, "")
                    tokens = cast(List[StringObject],
                                  [t for t in array_obj[1:-1] if
                                   isinstance(t, StringObject)])
                    yield Text(b"".join(t.bs for t in tokens))
                elif token_bytes == b"Td":
                    tx, ty = stack
                    yield Td(tx, ty)
                elif token_bytes == b"TD":
                    tx, ty = stack
                    yield TD(tx, ty)
                elif token_bytes in (
                        b"B", b"BX",
                        b"c", b"cs", b"CS", b"d", b"Do", b"EX", b"G", b"i",
                        b"scn", b"SCN", b"re", b"f",
                        b"g", b"h", b"j", b"J", b"l", b"m", b"M",
                        b"T", b"*", b"v", b"w", b"W", b"n", b"S", b"sh", b"y"
                ):
                    pass
                else:
                    raise ValueError("Invalid content token {}".format(token))

                stack = []
            else:
                stack.append(token)

    def parse_to_unicode(self, stream_wrapper: StreamWrapper
                         ) -> Mapping[int, str]:
        """
        9.7.5.4 CMap Example and Operator Summary

        :param stream_wrapper:
        :return:
        """
        stack = []

        fchar_count = 0
        frange_count = 0
        encoding = {}
        for token in PDFTokenizer(stream_wrapper):
            if isinstance(token, WordToken):
                token_bytes = token.bs
                if token_bytes == b"beginbfchar":
                    fchar_count = checked_cast(NumberObject, stack[0]).value
                elif token_bytes == b"endbfchar":
                    for i in range(0, fchar_count, 2):
                        first = checked_cast(StringObject, stack[i]).bs
                        second = checked_cast(StringObject, stack[i + 1]).bs
                        code = int.from_bytes(first, "big")
                        encoding[code] = second.decode("utf-16-be")
                elif token_bytes == b"beginbfrange":
                    frange_count = checked_cast(NumberObject, stack[0]).value
                elif token_bytes == b"endbfrange":
                    for i in range(0, frange_count, 3):
                        first = checked_cast(StringObject, stack[i]).bs
                        second = checked_cast(StringObject, stack[i + 1]).bs
                        third = stack[i + 2]
                        first_code = int.from_bytes(first, "big")
                        second_code = int.from_bytes(second, "big")
                        if isinstance(third, ArrayObject):
                            for code, value in enumerate(third, first_code):
                                bs = checked_cast(StringObject, value).bs
                                encoding[code] = bs.decode("utf-16-be")
                        elif isinstance(third, StringObject):
                            cur_value = third.bs.decode("utf-16-be")
                            for code in range(first_code, second_code):
                                encoding[code] = cur_value
                                cur_value = chr(ord(cur_value) + 1)
                        else:
                            raise ValueError()

                stack = []
            else:
                stack.append(token)
        return encoding
