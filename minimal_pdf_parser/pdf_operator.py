import logging
from typing import Any, List

from base import checked_cast, NumberObject, StringObject, OpenArrayToken, \
    CloseArrayToken
from pdf_operation import *
from pdf_operation import StrokePath


class TokenStack:
    _logger = logging.getLogger(__name__)

    def __init__(self):
        self._arr = []

    def push(self, element: Any):
        self._arr.append(element)

    def ignore(self):
        if self._arr:
            self._logger.warning("Stack err: %s (empty)", self._arr)
            self.clear()

    def pop(self) -> Any:
        if not self._arr:
            self._logger.warning("Stack err: %s (empty)", self._arr)
            return None

        return self._arr.pop(0)

    def pop_arr(self) -> List[Any]:
        token = self.pop()
        if token is not OpenArrayToken:
            self._logger.warning("Expected open array, was: %s", token)
        ret = []
        token = self.pop()
        while token and token is not CloseArrayToken:
            ret.append(token)
            token = self.pop()
        return ret

    def pop_n(self, n: int = 1) -> List[Any]:
        if len(self._arr) == n:
            ret = self._arr[:]
        elif len(self._arr) < n:
            self._logger.warning("Stack err: %s (%s)", self._arr, n)
            ret = self._arr + [None] * (n - len(self._arr))
        else:  # len(stack: TokenStack) > n:
            self._logger.warning("Stack err: %s (%s)", self._arr, n)
            ret = self._arr[:n]

        assert len(ret) == n
        self.clear()
        return ret

    def clear(self):
        self._arr.clear()


class Operator:
    def build(self, stack: TokenStack) -> List[Operation]:
        """Ignore operator or override this method !"""
        stack.clear()
        return []


# Table 57 – Graphics State Operators

class SaveCurGraphicsStateOperator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        stack.ignore()
        return [SaveCurGraphicsState()]


class RestoreCurGraphicsStateOperator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        stack.ignore()
        return [RestoreCurGraphicsState()]


class ModifyCTMOperator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        a, b, c, d, e, f = [checked_cast(NumberObject, x).value for x in stack.pop_n(6)]
        return [ModifyCTM(a, b, c, d, e, f)]


class SetLineWidthOperator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        width = checked_cast(NumberObject, stack.pop()).value
        return [SetLineWidth(width)]


class SetLineCapOperator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        cap = checked_cast(NumberObject, stack.pop()).value
        return [SetLineCap(cap)]


class SetLineJoinOperator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        join = stack.pop()
        return [SetLineJoin(join)]


class SetMiterLimitOperator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        miter_limit = stack.pop()
        return [SetMiterLimit(miter_limit)]


class SetLineDashPatternOperator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        dash_array = stack.pop_arr() # array of numbers
        dash_phase = stack.pop() # number
        return [SetLineDashPattern(dash_array, dash_phase)]


class SetColourRenderingIntentOperator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        intent = stack.pop()
        return [SetColourRenderingIntent(intent)]


class SetFlatnessToleranceOperator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        flatness = stack.pop()
        return [SetFlatnessTolerance(flatness)]


class SetParametersOperator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        dict_name = stack.pop()
        return [SetParameters(dict_name)]


# Table 59 – Path Construction Operators

class BeginSubpathOperator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        x, y = stack.pop_n(2)
        return [BeginSubpath(x, y)]


class AppendStraightLineOperator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        x, y = stack.pop_n(2)
        return [AppendStraightLine(x, y)]


class AppendCubicBezier1Operator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        x1, y1, x2, y2, x3, y3 = stack.pop_n(6)
        return [AppendCubicBezier1(x1, y1, x2, y2, x3, y3)]


class AppendCubicBezier2Operator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        x2, y2, x3, y3 = stack.pop_n(4)
        return [AppendCubicBezier2(x2, y2, x3, y3)]


class AppendCubicBezier3Operator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        x1, y1, x3, y3 = stack.pop_n(4)
        return [AppendCubicBezier3(x1, y1, x3, y3)]


class ClosePathOperator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        stack.ignore()
        return [ClosePath()]


class AppendRectangleOperator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        x, y, w, h = stack.pop_n(4)
        return [AppendRectangle(x, y, w, h)]


# Table 60 – Path-Painting Operators

class StrokePathOperator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        stack.ignore()
        return [StrokePath()]


class CloseAndStrokePathOperator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        stack.ignore()
        return [ClosePath(), StrokePath()]


class FillPathNZWOperator(
    Operator):  # Equivalent to f; included only for compatibility
    pass


class FillPathOEROperator(Operator):
    pass


class FillAndStrokePathNZWOperator(Operator):
    pass


class FillAndStrokePathOEROperator(Operator):
    pass


class CloseFillAndStrokePathNZWOperator(Operator):
    pass


class CloseFillAndStrokePathOEROperator(Operator):
    pass


class EndPathOperator(Operator):
    pass


# Table 61 – Clipping Path Operators

class IntersectNZWOperator(Operator):
    pass


class IntersectOEROperator(Operator):
    pass


# Table 107 – Text object operators

class BeginTextOperator(Operator):
    pass


class EndTextOperator(Operator):
    pass


# Table 108 – Text-positioning operators

class MoveStartNextLineOperator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        tx, ty = [checked_cast(NumberObject, x).value for x in stack.pop_n(2)]
        return [MoveStartNextLine(tx, ty)]

class MoveStartNextLineTextStateOperator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        tx, ty = [checked_cast(NumberObject, x).value for x in stack.pop_n(2)]
        return [MoveStartNextLineTextState(tx, ty)]

class SetTextMatrixOperator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        a, b, c, d, e, f = [checked_cast(NumberObject, x).value for x in stack.pop_n(6)]
        return [SetTextMatrix(a, b, c, d, e, f)]


class MoveStartNextLineWoParamsOperator(Operator):
    pass


# Table 109 – Text-showing operators

class ShowTextStringOperator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        bs = checked_cast(StringObject, stack.pop()).bs
        return [MoveStartNextLineWoParams(), ShowTextString(bs)]


class MoveStartNextLineAndShowTextStringOperator(Operator):
    def build(self, stack: TokenStack) -> List[Operation]:
        bs = checked_cast(StringObject, stack.pop()).bs
        return [ShowTextString(bs)]


class MoveStartNextLineAndShowTextStringWWordSpacingOperator(Operator):
    pass


class ShowTextStringsOperator(Operator):
    _logger = logging.getLogger(__name__)
    def build(self, stack: TokenStack) -> List[Operation]:
        arr = stack.pop_arr()
        ret = []
        for token in arr:
            if isinstance(token, StringObject):
                ret.append(ShowTextString(token.bs))
            elif isinstance(token, NumberObject):
                ret.append(SetTextMatrix(1, 0, 0, 1, token.value, 0))
            else:
                self._logger.warning("Unexpected TD array token %s", token)

        return ret

# Table 113 – Type 3 font operators

class SetGlyphWidthOperator(Operator):
    pass


class SetGlyphBBOperator(Operator):
    pass


# Table 74 – Colour Operators

class SetCurColourSpace1Operator(Operator):
    pass


class SetCurColourSpace1NonStrokingOperator(Operator):
    pass


class SetCurColourSpace2Operator(Operator):
    pass


class SetCurColourSpace3Operator(Operator):
    pass


class SetCurColourSpace2NonStrokingOperator(Operator):
    pass


class SetCurColourSpace3NonStrokingOperator(Operator):
    pass


class SetStrokingColourSpaceToGrayOperator(Operator):
    pass


class SetStrokingColourSpaceToGrayNonStrokingOperator(Operator):
    pass


class SetStrokingColourSpaceToRGBOperator(Operator):
    pass


class SetStrokingColourSpaceToRGBNonStrokingOperator(Operator):
    pass


class SetStrokingColourSpaceToCMYKOperator(Operator):
    pass


class SetStrokingColourSpaceToCMYKNonStrokingOperator(Operator):
    pass


# Table 77 – Shading Operator

class PaintShapeOperator(Operator):
    pass


# Table 92 – Inline Image Operators

class BeginInlineImageOperator(Operator):
    pass


class BeginInlineImageDataOperator(Operator):
    pass


class EndInlineImageOperator(Operator):
    pass


# Table 87 – XObject Operator

class PaintXObjectOperator(Operator):
    pass


# Table 320 – Marked-content operators

class MarkedContentOperator(Operator):
    pass


class MarkedContentWListOperator(Operator):
    pass


class BeginMarkedContentOperator(Operator):
    pass


class BeginMarkedContentWPropertiesOperator(Operator):
    pass


class EndMarkedContentOperator(Operator):
    pass


# Table 32 – Compatibility operators
class BeginCompatibilityOperator(Operator):
    pass


class EndCompatibilityOperator(Operator):
    pass


################################################
# Table 105 – Text state operators

class SetCharSpacingOperator(Operator):
    pass

class SetWordSpacingOperator(Operator):
    pass

class SetHorizScalingOperator(Operator):
    pass

class SetTextLeadingOperator(Operator):
    pass

class SetFontSizeOperator(Operator):
    pass

class SetTextRenderingModeOperator(Operator):
    pass

class SetTextRiseOperator(Operator):
    pass

operator_by_token_bytes = {
    # Table 57 – Graphics State Operators
    b"q": SaveCurGraphicsStateOperator(),
    b"Q": RestoreCurGraphicsStateOperator(),
    b"cm": ModifyCTMOperator(),
    b"w": SetLineWidthOperator(),
    b"J": SetLineCapOperator(),
    b"j": SetLineJoinOperator(),
    b"M": SetMiterLimitOperator(),
    b"d": SetLineDashPatternOperator(),
    b"ri": SetColourRenderingIntentOperator(),
    b"i": SetFlatnessToleranceOperator(),
    b"gs": SetParametersOperator(),

    b"m": BeginSubpathOperator(),
    b"l": AppendStraightLineOperator(),
    b"c": AppendCubicBezier1Operator(),
    b"v": AppendCubicBezier2Operator(),
    b"y": AppendCubicBezier3Operator(),
    b"h": ClosePathOperator(),
    b"re": AppendRectangleOperator(),

    # Table 60 – Path-Painting Operators
    b"S": StrokePathOperator(),
    b"s": CloseAndStrokePathOperator(),
    b"f": FillPathNZWOperator(),
    b"F": FillPathNZWOperator(),
    # Equivalent to f; included only for compatibility.
    b"f*": FillPathOEROperator(),
    b"B": FillAndStrokePathNZWOperator(),
    b"B*": FillAndStrokePathOEROperator(),
    b"b": CloseFillAndStrokePathNZWOperator(),
    b"b*": CloseFillAndStrokePathOEROperator(),
    b"n": EndPathOperator(),

    # Table 61 – Clipping Path Operators
    b"W": IntersectNZWOperator(),
    b"W*": IntersectOEROperator(),

    # Table 107 – Text object operators
    b"BT": BeginTextOperator(),
    b"ET": EndTextOperator(),

    # Table 108 – Text-positioning operators
    b"Td": MoveStartNextLineOperator(),
    b"TD": MoveStartNextLineTextStateOperator(),
    b"Tm": SetTextMatrixOperator(),
    b"T*": MoveStartNextLineWoParamsOperator(),

    # Table 109 – Text-showing operators
    b"Tj": ShowTextStringOperator(),
    b"'": MoveStartNextLineAndShowTextStringOperator(),
    b"\"": MoveStartNextLineAndShowTextStringWWordSpacingOperator(),
    b"TJ": ShowTextStringsOperator(),

    # Table 113 – Type 3 font operators
    b"d0": SetGlyphWidthOperator(),
    b"d1": SetGlyphBBOperator(),

    # Table 74 – Colour Operators
    b"CS": SetCurColourSpace1Operator(),
    b"cs": SetCurColourSpace1NonStrokingOperator(),
    b"SC": SetCurColourSpace2Operator(),
    b"SCN": SetCurColourSpace3Operator(),
    b"sc": SetCurColourSpace2NonStrokingOperator(),
    b"scn": SetCurColourSpace3NonStrokingOperator(),
    b"G": SetStrokingColourSpaceToGrayOperator(),
    b"g": SetStrokingColourSpaceToGrayNonStrokingOperator(),
    b"RG": SetStrokingColourSpaceToRGBOperator(),
    b"rg": SetStrokingColourSpaceToRGBNonStrokingOperator(),
    b"K": SetStrokingColourSpaceToCMYKOperator(),
    b"k": SetStrokingColourSpaceToCMYKNonStrokingOperator(),

    # Table 77 – Shading Operator
    b"sh": PaintShapeOperator(),

    # Table 92 – Inline Image Operators
    b"BI": BeginInlineImageOperator(),
    b"ID": BeginInlineImageDataOperator(),
    b"EI": EndInlineImageOperator(),

    # Table 87 – XObject Operator
    b"Do": PaintXObjectOperator(),

    # Table 320 – Marked-content operators
    b"MP": MarkedContentOperator(),
    b"DP": MarkedContentWListOperator(),
    b"BMC": BeginMarkedContentOperator(),
    b"BDC": BeginMarkedContentWPropertiesOperator(),
    b"EMC": EndMarkedContentOperator(),

    # Table 32 – Compatibility operators
    b"BX": BeginCompatibilityOperator(),
    b"EX": EndCompatibilityOperator(),

    ################################################
    # Table 105 – Text state operators
    b"Tc": SetCharSpacingOperator(),
    b"Tw": SetWordSpacingOperator(),
    b"Tz": SetHorizScalingOperator(),
    b"TL": SetTextLeadingOperator(),
    b"Tf": SetFontSizeOperator(),
    b"Tr": SetTextRenderingModeOperator(),
    b"Ts": SetTextRiseOperator(),
}
