from typing import Any, Final

import attrs

from .alias import AliasMX, extract_alias
from .cast import CastMX
from .column import prepare_column
from .distinct import DistinctMX
from .literal import Literal
from .marks import MARKS_FIELD, MARKS_TYPE
from .operation import OperationMX
from .operators import And, Or
from .order_by import OrderByMX
from .param import Param
from .utils import ITERABLES, RE_PARENTHESIZED, CompileABC, SelectMX


_NOT_SET = object()


def _convert_right(value):
    if not isinstance(value, CompileABC):
        value = Param(value)

    return value


@attrs.frozen(eq=False)
class Operation(CompileABC, CastMX, AliasMX, DistinctMX, OrderByMX, OperationMX, SelectMX):
    _left: Any = attrs.field(alias='left')
    _right: Any = attrs.field(alias='right', converter=_convert_right)
    _marks: MARKS_TYPE = MARKS_FIELD

    def _build(self, params: list) -> str:
        raise NotImplementedError


_NULL_BOOL: Final[tuple] = (type(None), bool)


def _check_null_or_bool(left, right) -> bool:
    for i in (left, right):
        if isinstance(i, (Literal, Param)) and isinstance(i._value, _NULL_BOOL):
            return True

    return False


def _build(elem, params: list) -> str:
    from .select import Select

    res = elem._build(params)
    if (
        (isinstance(elem, Operation) and not RE_PARENTHESIZED.fullmatch(res))
        or isinstance(elem, Select)
    ):
        res = '(%s)' % res
    return res


def _wrap_operation_member(item) -> str:
    if isinstance(item, (And, Or)):
        return '(%s)'
    else:
        return '%s'


@attrs.frozen(eq=False)
class OperationEquality(Operation):
    _operator_equal: str = attrs.field(alias='operator_eq', default=_NOT_SET)
    _operator_is: str = attrs.field(alias='operator_is', default=_NOT_SET)

    def __attrs_post_init__(self):
        if self._operator_equal is _NOT_SET:
            raise ValueError
        elif self._operator_is is _NOT_SET:
            raise ValueError

    def _build(self, params: list) -> str:
        if alias := extract_alias(self):
            return alias

        if _check_null_or_bool(self._left, self._right):
            op = self._operator_is
        else:
            op = self._operator_equal

        expr = '%s %s %s' % (
            _wrap_operation_member(self._left),
            op,
            _wrap_operation_member(self._right),
        )
        res = expr % (
            _build(self._left, params),
            _build(self._right, params),
        )
        if self._marks:
            res = self._marks.build(res)
        return res


@attrs.frozen(eq=False)
class OperationMath(Operation):
    _operator: str = attrs.field(alias='operator', default=_NOT_SET)

    def __attrs_post_init__(self):
        if self._operator is _NOT_SET:
            raise ValueError

    def _build(self, params: list) -> str:
        if alias := extract_alias(self):
            return alias

        expr = '%s %s %s' % (
            _wrap_operation_member(self._left),
            self._operator,
            _wrap_operation_member(self._right),
        )
        res = expr % (
            _build(self._left, params),
            _build(self._right, params),
        )
        if self._marks:
            res = self._marks.build(res)
        return res


def _convert_items(value):
    from .select import Select

    if isinstance(value, ITERABLES):
        if not value:
            raise ValueError
        value = tuple(prepare_column(i) for i in value)
    else:
        if not isinstance(value, Select):
            raise TypeError(value)

    return value


@attrs.frozen(eq=False)
class OperationIn(CompileABC, CastMX, AliasMX, DistinctMX, OrderByMX, OperationMX, SelectMX):
    _left: Any = attrs.field(alias='left')
    _items: CompileABC | tuple[CompileABC, ...] = attrs.field(
        alias='items',
        converter=_convert_items,
    )
    _marks: MARKS_TYPE = MARKS_FIELD
    _operator: str = attrs.field(alias='operator', default='IN')

    def _build(self, params: list) -> str:
        if alias := extract_alias(self):
            return alias

        expr = '%s %s' % (_wrap_operation_member(self._left), self._operator)
        res = expr % _build(self._left, params)

        if isinstance(self._items, tuple):
            res = '%s (%s)' % (res, ', '.join(i._build(params) for i in self._items))
        else:
            res = '%s (%s)' % (res, self._items._build(params))

        if self._marks:
            res = self._marks.build(res)
        return res


@attrs.frozen(eq=False)
class OperationBetween(CompileABC, CastMX, AliasMX, DistinctMX, OrderByMX, OperationMX, SelectMX):
    _left: Any = attrs.field(alias='left')
    _start: CompileABC = attrs.field(alias='start', converter=prepare_column)
    _end: CompileABC = attrs.field(alias='end', converter=prepare_column)
    _marks: MARKS_TYPE = MARKS_FIELD

    def _build(self, params: list) -> str:
        if alias := extract_alias(self):
            return alias

        expr = '%s BETWEEN %%s AND %%s' % _wrap_operation_member(self._left)
        res = expr % (
            _build(self._left, params),
            _build(self._start, params),
            _build(self._end, params),
        )
        if self._marks:
            res = self._marks.build(res)
        return res


@attrs.frozen(eq=False)
class OperationAny(Operation):
    def _build(self, params: list) -> str:
        if alias := extract_alias(self):
            return alias

        expr = '%s = ANY(%%s)' % _wrap_operation_member(self._left)
        res = expr % (
            _build(self._left, params),
            _build(self._right, params),
        )
        if self._marks:
            res = self._marks.build(res)
        return res


@attrs.frozen(eq=False)
class OperationLike(Operation):
    _operator: str = attrs.field(alias='operator', default='LIKE')

    def _build(self, params: list) -> str:
        if alias := extract_alias(self):
            return alias

        expr = '%s %%s %%s' % _wrap_operation_member(self._left)
        res = expr % (
            _build(self._left, params),
            self._operator,
            _build(self._right, params),
        )
        if self._marks:
            res = self._marks.build(res)
        return res


@attrs.frozen(eq=False)
class OperationCustom(Operation):
    _operator: str = attrs.field(alias='operator', default=_NOT_SET)

    def __attrs_post_init__(self):
        if self._operator is _NOT_SET:
            raise ValueError

    def _build(self, params: list) -> str:
        if alias := extract_alias(self):
            return alias

        expr = '%s %s %%s' % (_wrap_operation_member(self._left), self._operator)
        res = expr % (
            _build(self._left, params),
            _build(self._right, params),
        )
        if self._marks:
            res = self._marks.build(res)
        return res
