class Operation:
    def __repr__(self) -> str:
        return "{}({})".format(self.__class__.__name__, ",".join(
            ["{}={}".format(x, y) for x, y in self.__dict__.items()]))


# Table 57 – Graphics State Operators

class SaveCurGraphicsState(Operation):
    pass


class RestoreCurGraphicsState(Operation):
    pass


class ModifyCTM(Operation):
    """
    8.3.4 Transformation Matrices
    x′ = a × x + c × y + e
    y′ = b × x + d × y + f
    """

    def __init__(self, a, b, c, d, e, f):
        self.a = a
        self.b = b
        self.c = c
        self.d = d
        self.e = e
        self.f = f


class SetLineWidth(Operation):
    def __init__(self, width):
        self.width = width


class SetLineCap(Operation):
    def __init__(self, cap):
        self.cap = cap


class SetLineJoin(Operation):
    def __init__(self, join):
        self.join = join


class SetMiterLimit(Operation):
    def __init__(self, miter_limit):
        self.miter_limit = miter_limit


class SetLineDashPattern(Operation):
    def __init__(self, dash_array, dash_phase):
        self.dash_array = dash_array
        self.dash_phase = dash_phase


class SetColourRenderingIntent(Operation):
    def __init__(self, intent):
        self.intent = intent


class SetFlatnessTolerance(Operation):
    def __init__(self, flatness):
        self.flatness = flatness


class SetParameters(Operation):
    def __init__(self, dict_name):
        self.dict_name = dict_name


# Table 59 – Path Construction Operators

class BeginSubpath(Operation):
    def __init__(self, x, y):
        self.x = x
        self.y = y


class AppendStraightLine(Operation):
    def __init__(self, x, y):
        self.x = x
        self.y = y


class AppendCubicBezier1(Operation):
    def __init__(self, x1, y1, x2, y2, x3, y3):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.x3 = x3
        self.y3 = y3


class AppendCubicBezier2(Operation):
    def __init__(self, x2, y2, x3, y3):
        self.x2 = x2
        self.y2 = y2
        self.x3 = x3
        self.y3 = y3


class AppendCubicBezier3(Operation):
    def __init__(self, x1, y1, x3, y3):
        self.x1 = x1
        self.y1 = y1
        self.x3 = x3
        self.y3 = y3


class ClosePath(Operation):
    pass


class AppendRectangle(Operation):
    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h


# Table 60 – Path-Painting Operators

class StrokePath(Operation):
    pass


#
class SetFont(Operation):
    def __init__(self, name: bytes, size: int):
        self.name = name
        self.size = size


# Table 108 – Text-positioning operators

class SetTextMatrix(Operation):
    """
    See Table 108 – Text-positioning operators (continued)
    """

    def __init__(self, a, b, c, d, e, f):
        self.a = a
        self.b = b
        self.c = c
        self.d = d
        self.e = e
        self.f = f


# Table 109 – Text-showing operators
class ShowTextString(Operation):
    def __init__(self, bs: bytes):
        self.bs = bs


class MoveStartNextLineWoParams(Operation):
    pass


class MoveStartNextLine(Operation):
    def __init__(self, tx: float, ty: float):
        self.tx = tx
        self.ty = ty


class MoveStartNextLineTextState(Operation):
    def __init__(self, tx: float, ty: float):
        self.tx = tx
        self.ty = ty


__all__ = ['AppendCubicBezier1', 'AppendCubicBezier2', 'AppendCubicBezier3',
           'AppendRectangle', 'AppendStraightLine', 'BeginSubpath', 'ClosePath',
           'ModifyCTM', 'MoveStartNextLine', 'MoveStartNextLineTextState',
           'MoveStartNextLineWoParams', 'Operation',
           'RestoreCurGraphicsState',
           'SaveCurGraphicsState', 'SetColourRenderingIntent',
           'SetFlatnessTolerance', 'SetFont', 'SetLineCap',
           'SetLineDashPattern', 'SetLineJoin', 'SetLineWidth', 'SetMiterLimit',
           'SetParameters', 'ShowTextString', 'SetTextMatrix']  # 'TD', 'Td',
