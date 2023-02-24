from copy import deepcopy
from datetime import date, datetime
from types import MappingProxyType
from typing import Any, Final

import attrs

from .alias import AliasMX, extract_alias
from .cast import CastMX
from .distinct import DistinctMX
from .marks import MARKS_FIELD, MARKS_TYPE
from .operation import OperationMX
from .order_by import OrderByMX
from .utils import CompileABC, SelectMX


_TYPES: Final[MappingProxyType] = MappingProxyType({
    int: lambda x: str(x),
    float: lambda x: str(x),
    type(None): lambda x: 'NULL',
    bool: lambda x: str(x).upper(),
    str: lambda x: "'%s'" % x,
    date: lambda x: "'%s'" % x,
    datetime: lambda x: "'%s'" % x,
})


def _convert_value(value):
    if isinstance(value, (set, frozenset, list)):
        value = tuple(value)
    return deepcopy(value)


@attrs.frozen(repr=False, eq=False)
class Literal(CompileABC, CastMX, AliasMX, DistinctMX, OrderByMX, OperationMX, SelectMX):
    _value: Any = attrs.field(alias='value', converter=_convert_value)
    _marks: MARKS_TYPE = MARKS_FIELD

    @_value.validator
    def _vld_value(self, attribute, value):
        if isinstance(value, tuple):
            if not value:
                raise ValueError(value)
            elif bad := [i for i in value if type(i) not in _TYPES]:
                raise TypeError(bad)

    def _build(self, params: list) -> str:
        if alias := extract_alias(self):
            return alias

        if handler := _TYPES.get(type(self._value)):
            res = handler(self._value)
        elif isinstance(self._value, tuple):
            res = "ARRAY[%s]" % ', '.join(_TYPES[type(i)](i) for i in self._value)
        else:
            raise TypeError('unhandled type %s' % type(self._value))

        if self._marks:
            res = self._marks.build(res)
        return res

    def __repr__(self):
        res = 'Literal(%s)' % str(self._value)
        if self._marks:
            res += f':{repr(self._marks)}'
        return res


NULL: Final[Literal] = Literal(None)
