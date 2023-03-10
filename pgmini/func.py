from typing import Callable, Final

import attrs

from .alias import AliasMX, extract_alias
from .cast import CastMX
from .column import Column, prepare_column
from .distinct import DistinctMX
from .literal import Literal
from .marks import MARKS_FIELD, MARKS_TYPE
from .operation import OperationMX
from .order_by import OrderByMX, do_order_by
from .utils import (
    CTX_ALIAS_ONLY,
    ITERABLES,
    STAR_SIGN,
    CompileABC,
    FromABC,
    SelectMX,
    build_where,
    set_context,
    wrap_brackets_if_needed,
)


__all__ = ['F', 'Func']


def _convert_partition_by(value):
    if value is not None:
        if not isinstance(value, ITERABLES):
            value = (value,)
        return tuple(prepare_column(i) for i in value)


def _convert_order_by(value):
    if value is not None:
        if not isinstance(value, ITERABLES):
            value = (value,)
        return tuple(prepare_column(i) for i in value)


@attrs.frozen(kw_only=True)
class Over:
    partition_by: tuple | None = attrs.field(converter=_convert_partition_by, default=None)
    order_by: tuple | None = attrs.field(converter=_convert_order_by, default=None)

    def build(self, params: list) -> str:
        res = []
        if self.partition_by is not None:
            res.append('PARTITION BY %s' % ', '.join(
                i._build(params)
                for i in self.partition_by
            ))
        if self.order_by is not None:
            res.append('ORDER BY %s' % ', '.join(
                i._build(params)
                for i in self.order_by
            ))
        return 'OVER (%s)' % ' '.join(res)


STAR: Final[Literal] = Literal(STAR_SIGN)


def _converter_params(value):
    return tuple(
        STAR if isinstance(i, str) and i == STAR_SIGN else prepare_column(i)
        for i in value
    )


@attrs.frozen(eq=False, unsafe_hash=True)
class _Func(CompileABC, FromABC, CastMX, AliasMX, DistinctMX, OrderByMX, OperationMX, SelectMX):
    _name: str = attrs.field(alias='x_name', converter=lambda x: x.upper())
    _params: tuple[CompileABC, ...] = attrs.field(alias='x_params', converter=_converter_params)
    _over: Over | None = attrs.field(alias='x_over', default=None)
    _where: tuple[CompileABC, ...] = attrs.field(alias='x_where', factory=tuple)
    _order_by: tuple[CompileABC, ...] = attrs.field(alias='x_order_by', factory=tuple)
    _marks: MARKS_TYPE = MARKS_FIELD

    def Over(self, *, partition_by=None, order_by=None):
        return attrs.evolve(self, x_over=Over(partition_by=partition_by, order_by=order_by))

    def Where(self, *statements: CompileABC):
        return attrs.evolve(self, x_where=statements)

    def OrderBy(self, *statements):
        return do_order_by(self, statements)

    def _build(self, params: list) -> str:
        if alias := extract_alias(self):
            return alias

        args = ', '.join(
            (
                STAR_SIGN
                if isinstance(i, Literal) and i._value == STAR_SIGN and self._name == 'COUNT'
                else wrap_brackets_if_needed(i._build(params), obj=i)
            )
            for i in self._params
        )
        if self._order_by:
            with set_context({CTX_ALIAS_ONLY: True}):
                if self._order_by:
                    args = '%s ORDER BY %s' % (
                        args,
                        ', '.join(i._build(params) for i in self._order_by)
                    )

        parts = ['%s(%s)' % (self._name, args)]
        if self._over is not None:
            parts.append(self._over.build(params))

        if self._where:
            parts.append('FILTER (%s)' % build_where(self._where, params=params))

        res = ' '.join(parts)
        if self._marks:
            res = self._marks.build(res)
        return res

    def _get_from_statement(self, params: list) -> str:
        return self._build(params)

    def _get_name(self) -> str:
        return self._name

    STAR: Final[Column] = Column(STAR_SIGN, table=None)

    def __getattribute__(self, item: str) -> Column:
        try:
            return object.__getattribute__(self, item)
        except AttributeError:
            return Column(item, table=None)


class FuncCls:
    def __getattribute__(self, item: str) -> Callable[..., _Func]:
        return lambda *params: _Func(x_name=item, x_params=params)


F = Func = FuncCls()
