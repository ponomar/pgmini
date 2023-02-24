from __future__ import annotations

from functools import partial
from typing import Any, Literal as LiteralT

import attrs

from .cast import build_cast
from .column import Column, prepare_column
from .literal import Literal
from .operators import And
from .order_by import do_order_by
from .param import Param
from .subquery import Subquery
from .utils import (
    CTX_ALIAS_ONLY,
    CTX_CTE,
    CTX_TABLES,
    CompileABC,
    FromABC,
    SelectMX,
    build_from,
    build_where,
    build_with,
    set_context,
    wrap_brackets_if_needed,
)


def _convert_on_statement(value):
    if value is True:
        value = Literal(True)
    return value


@attrs.frozen
class _Join:
    type: LiteralT['left', 'right'] = attrs.field(validator=attrs.validators.in_({'left', 'right'}))
    table: FromABC
    on_statement: Any = attrs.field(converter=_convert_on_statement)
    lateral: bool = attrs.field(validator=attrs.validators.in_({True, False}), default=False)

    def _build(self, params: list):
        if self.type == 'right':
            sql = 'JOIN'
        else:
            sql = 'LEFT JOIN'

        cte = self.table in CTX_CTE.get()
        if self.lateral:
            if cte:
                raise ValueError
            sql = '%s LATERAL' % sql

        return '%s %s ON %s' % (
            sql,
            self.table._get_name() if cte else self.table._get_from_statement(params),
            self.on_statement._build(params),
        )


@attrs.frozen
class _Union:
    type: LiteralT['distinct', 'all'] = attrs.field(
        validator=attrs.validators.in_({'distinct', 'all'}),
    )
    select: Select

    def _build(self, params: list) -> str:
        expr = 'UNION'
        if self.type == 'all':
            expr = '%s ALL' % expr
        return '%s %s' % (expr, self.select._build(params))


def _convert_columns(values):
    return tuple(prepare_column(i) for i in values)


def _convert_limit(value):
    if not (value is None or isinstance(value, CompileABC)):
        value = Param(value)
    return value


def _convert_offset(value):
    if not (value is None or isinstance(value, CompileABC)):
        value = Param(value)
    return value


@attrs.frozen(init=False)
class Select(CompileABC, SelectMX):
    _columns: tuple[CompileABC, ...] = attrs.field(alias='x_columns', converter=_convert_columns)
    _with: tuple[Subquery, ...] = attrs.field(alias='x_with', factory=tuple)
    _from: tuple[FromABC, ...] = attrs.field(alias='x_from', factory=tuple)
    _join: tuple[_Join, ...] = attrs.field(alias='x_join', factory=tuple)
    _where: tuple[CompileABC, ...] = attrs.field(alias='x_where', factory=tuple)
    _group_by: tuple[CompileABC, ...] = attrs.field(alias='x_group_by', factory=tuple)
    _having: tuple[CompileABC, ...] = attrs.field(alias='x_having', factory=tuple)
    _distinct_on: tuple[CompileABC, ...] = attrs.field(alias='x_distinct_on', factory=tuple)
    _order_by: tuple[CompileABC, ...] = attrs.field(alias='x_order_by', factory=tuple)
    _limit: CompileABC | None = attrs.field(alias='x_limit', converter=_convert_limit, default=None)
    _offset: CompileABC | None = attrs.field(
        alias='x_offset',
        converter=_convert_offset,
        default=None,
    )
    _union: tuple[_Union, ...] = attrs.field(alias='x_union', factory=tuple)
    _cast: str | None = attrs.field(alias='x_cast', default=None)
    _alias: str | None = attrs.field(alias='x_alias', default=None)

    def __init__(self, *columns, **kwargs):
        kwargs.setdefault('x_columns', columns)
        self.__attrs_init__(**kwargs)

    @_columns.validator
    def _vld_columns(self, attribute, value):
        if not value:
            raise ValueError

    @_from.validator
    def _vld_from(self, attribute, value):
        if bad := [i for i in value if not isinstance(i, FromABC)]:
            raise ValueError(bad)

    @_distinct_on.validator
    def _vld_distinct_on(self, attribute, value):
        if bad := [i for i in value if not isinstance(i, CompileABC)]:
            raise TypeError(bad)

    def AddColumns(self, *columns):
        return attrs.evolve(self, x_columns=self._columns + columns)

    def GetColumns(self) -> tuple[str, ...]:
        res = []
        for i in self._columns:
            if i._marks and i._marks.alias:
                name = i._marks.alias
            elif isinstance(i, Column):
                name = i._name
            else:
                name = None

            res.append(name)

        return tuple(res)

    def From(self, *froms):
        return attrs.evolve(self, x_from=froms)

    def Join(self, other: FromABC, on_statement):
        return attrs.evolve(
            self,
            x_join=self._join + (_Join('right', other, on_statement=on_statement),),
        )

    def LeftJoin(self, other: FromABC, on_statement):
        return attrs.evolve(
            self,
            x_join=self._join + (_Join('left', other, on_statement=on_statement),),
        )

    def JoinLateral(self, other: FromABC, on_statement):
        return attrs.evolve(
            self,
            x_join=self._join + (_Join('right', other, on_statement=on_statement, lateral=True),),
        )

    def LeftJoinLateral(self, other: FromABC, on_statement):
        return attrs.evolve(
            self,
            x_join=self._join + (_Join('left', other, on_statement=on_statement, lateral=True),),
        )

    def Where(self, *statements: CompileABC):
        """New statements will be added to old ones"""
        return attrs.evolve(self, x_where=self._where + statements)

    def GroupBy(self, *statements: CompileABC):
        if self._group_by != ():
            raise ValueError(self._group_by)
        return attrs.evolve(self, x_group_by=statements)

    def Having(self, *statements: CompileABC):
        """New statements will be added to old ones"""
        return attrs.evolve(self, x_having=self._having + statements)

    def DistinctOn(self, *statements: CompileABC):
        return attrs.evolve(self, x_distinct_on=statements)

    def OrderBy(self, *statements):
        """
        None will remove ORDER BY if was set.
        New statements will be added to old ones.
        """
        return do_order_by(self, statements)

    def Limit(self, value):
        """None will remove LIMIT if was set."""
        return attrs.evolve(self, x_limit=value)

    def Offset(self, value):
        """None will remove OFFSET if was set."""
        return attrs.evolve(self, x_offset=value)

    def Union(self, other: Select):
        return attrs.evolve(self, x_union=self._union + (_Union('distinct', select=other),))

    def UnionAll(self, other: Select):
        return attrs.evolve(self, x_union=self._union + (_Union('all', select=other),))

    def As(self, alias: str):
        return attrs.evolve(self, x_alias=alias)

    def Cast(self, to: str):
        return attrs.evolve(self, x_cast=to)

    def Subquery(self, alias: str, materialized: bool = False):
        return Subquery(self, alias=alias, materialized=materialized)

    def _build(self, params: list) -> str:
        parts = []

        if self._with:
            if CTX_CTE.get():
                raise ValueError
            CTX_CTE.set(self._with)
            parts.append(build_with(self._with, params))

        ctx = partial(set_context, {CTX_TABLES: self._from + tuple(i.table for i in self._join)})

        with ctx():
            if self._distinct_on:
                select = (
                    'SELECT DISTINCT ON (%s)'
                    % ', '.join(dst._build(params) for dst in self._distinct_on)
                )
            else:
                select = 'SELECT'

            parts.append('%s %s' % (select, ', '.join(
                wrap_brackets_if_needed(i._build(params), obj=i)
                for i in self._columns
            )))

        if self._from:
            parts.append(build_from(self._from, params))

        if self._join:
            parts.extend(obj._build(params) for obj in self._join)

        with ctx():
            if self._where:
                parts.append(build_where(self._where, params=params))

            with set_context({CTX_ALIAS_ONLY: True}):
                if self._group_by:
                    parts.append('GROUP BY %s' % ', '.join(
                        i._build(params) for i in self._group_by
                    ))

            if self._having:
                if len(self._having) > 1:
                    statements = And(*self._having)
                else:
                    statements = self._having[0]
                parts.append('HAVING %s' % statements._build(params))

            with set_context({CTX_ALIAS_ONLY: True}):
                if self._order_by:
                    parts.append('ORDER BY %s' % ', '.join(
                        i._build(params) for i in self._order_by
                    ))

            if self._limit is not None:
                parts.append('LIMIT %s' % self._limit._build(params))

            if self._offset is not None:
                parts.append('OFFSET %s' % self._offset._build(params))

        if self._union:
            for obj in self._union:
                parts.append(obj._build(params))

        res = ' '.join(parts)

        if self._cast is not None:
            res = build_cast(res, cast=self._cast)

        if self._alias is not None:
            res = '(%s) AS %s' % (res, self._alias)

        return res
