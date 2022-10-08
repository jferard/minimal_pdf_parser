from typing import NamedTuple, List, Any, Dict, Union, TypeVar, Type, cast


class _OpenDictTokenClass:
    def __repr__(self):
        return "OpenDictToken"


class _CloseDictTokenClass:
    def __repr__(self):
        return "CloseDictToken"


class _OpenArrayTokenClass:
    def __repr__(self):
        return "OpenArrayToken"


class _CloseArrayTokenClass:
    def __repr__(self):
        return "CloseArrayToken"


OpenDictToken = _OpenDictTokenClass()
CloseDictToken = _CloseDictTokenClass()
OpenArrayToken = _OpenArrayTokenClass()
CloseArrayToken = _CloseArrayTokenClass()

StringObject = NamedTuple("StringObject", [("bs", bytes)])

NameObject = NamedTuple("NameObject", [("bs", bytes)])
WordToken = NamedTuple("WordToken", [("bs", bytes)])


class ArrayObject:
    def __init__(self, arr: List[Any]):
        self._arr = arr

    def __repr__(self) -> str:
        return "ArrayObject(arr={})".format(self._arr)

    def __iter__(self):
        return self._arr.__iter__()


class DictObject:
    def __init__(self, d: Dict[bytes, Any]):
        self._d = d

    def __repr__(self) -> str:
        return "DictObject(object={})".format(repr(self._d))

    def __getitem__(self, item):
        return self._d.__getitem__(item)

    def get(self, item, default_value=None):
        return self._d.get(item, default_value)

    def items(self):
        return self._d.items()


BooleanObject = NamedTuple("BooleanObject", [("value", bool)])
NullObject = object()


class NumberObject:
    def __init__(self, bs: bytes):
        self._bs = bs

    def __repr__(self) -> str:
        return "NumberObject(bs={})".format(repr(self._bs))

    @property
    def value(self) -> Union[int, float]:
        if b"." in self._bs:
            return float(self._bs)
        else:
            return int(self._bs)


class IndirectRef:
    def __init__(self, obj_num: NumberObject, gen_num: NumberObject):
        self._obj_num = obj_num
        self._gen_num = gen_num

    def __repr__(self) -> str:
        return "IndirectRef(obj_num={}, gen_num={})".format(self._obj_num,
                                                            self._gen_num)

    @property
    def obj_num(self) -> int:
        return self._obj_num.value

    @property
    def gen_num(self) -> int:
        return self._gen_num.value


IndirectObject = NamedTuple("IndirectObject",
                            [("obj_num", int), ("gen_num", int),
                             ("object", Any)])


class StreamObject:
    def __init__(self, obj_num: int, gen_num: int, object: DictObject,
                 start: int, length: int):
        self.obj_num = obj_num
        self.gen_num = gen_num
        self.object = object
        self.start = start
        self.length = length

    def __repr__(self, ):
        return "StreamObject({}, {}, {}, {}, {})".format(self.obj_num,
                                                         self.gen_num,
                                                         self.object,
                                                         self.start,
                                                         self.length)


def get_num(dict_object: DictObject, key: bytes,
            default_value: Union[int, float] = None) -> Union[int, float]:
    try:
        value = checked_cast(NumberObject, dict_object[key]).value
    except KeyError:
        if default_value is None:
            raise
        value = default_value
    return value


def get_string(dict_object: DictObject, key: bytes,
               default_value: bytes = None) -> bytes:
    try:
        value = checked_cast(StringObject, dict_object[key]).bs
    except KeyError:
        if default_value is None:
            raise
        value = default_value
    return value


def check(value: bool, format_string: str, *parameters):
    if not value:
        raise Exception(format_string.format(*parameters))


T = TypeVar('T')


def checked_cast(typ: Type[T], val: Any) -> T:
    check(isinstance(val, typ), "Expected type {} for value {}", typ, val)
    return cast(typ, val)
