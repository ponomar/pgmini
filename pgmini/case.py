from typing import Any

import attrs

from .alias import AliasMX, extract_alias
from .cast import CastMX
from .column import prepare_column
from .distinct import DistinctMX
from .marks import MARKS_FIELD, MARKS_TYPE
from .operation import OperationMX
from .order_by import OrderByMX
from .utils import CompileABC, SelectMX


def _convert_statements(value):
    return tuple((op, prepare_column(val)) for op, val in value)


def _convert_else(value):
    if value is not None:
        return prepare_column(value)


@attrs.frozen(eq=False, init=False)
class Case(CompileABC, CastMX, AliasMX, DistinctMX, OrderByMX, OperationMX, SelectMX):
    _statements: tuple[tuple[CompileABC, CompileABC], ...] = attrs.field(
        alias='statements',
        converter=_convert_statements,
    )
    _else: CompileABC | None = attrs.field(alias='x_else', converter=_convert_else, default=None)
    _marks: MARKS_TYPE = MARKS_FIELD

    @_statements.validator
    def _vld_statements(self, attribute, value):
        if not value:
            raise ValueError
        elif bad := [op for op, _ in value if not isinstance(op, CompileABC)]:
            raise TypeError(bad)

    def __init__(self, *statements: tuple[Any, Any], Else=None, **kwargs):
        kwargs.setdefault('statements', statements)
        kwargs.setdefault('x_else', Else)
        self.__attrs_init__(**kwargs)

    def _build(self, params: list) -> str:
        if alias := extract_alias(self):
            return alias

        parts = []
        for op, val in self._statements:
            parts.append('WHEN %s THEN %s' % (op._build(params), val._build(params)))
        if self._else is not None:
            parts.append('ELSE %s' % self._else._build(params))
        res = 'CASE %s END' % ' '.join(parts)
        if self._marks:
            res = self._marks.build(res)
        return res
