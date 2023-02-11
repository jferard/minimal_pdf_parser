from typing import Iterator, Mapping

from base import (NumberObject,
    WordToken, checked_cast, StringObject, ArrayObject)
from tokenizer import (PDFTokenizer, StreamWrapper)
from pdf_operator import *

class ContentParser:
    _logger = logging.getLogger(__name__)

    def parse_content(self, stream_wrapper: StreamWrapper
                      ) -> Iterator[Operation]:
        stack = TokenStack()

        # See : Table A.1 – PDF content stream operators
        for token in PDFTokenizer(stream_wrapper):
            if isinstance(token, WordToken):
                token_bytes = token.bs
                try:
                    operator = operator_by_token_bytes[token_bytes]
                    for operation in operator.build(stack):
                        yield operation
                except KeyError:
                    self._logger.warning("Unk token name %s", token_bytes)
            else:
                stack.push(token)

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


