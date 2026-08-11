from __future__ import annotations

from functools import partial
from types import MappingProxyType
from typing import Any, Final

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


_JOIN_SQL: Final = MappingProxyType({
    'inner': 'JOIN',
    'left': 'LEFT JOIN',
    'right': 'RIGHT JOIN',
    'full': 'FULL JOIN',
    'cross': 'CROSS JOIN',
})


@attrs.frozen
class _Join:
    type: str = attrs.field(validator=attrs.validators.in_(_JOIN_SQL))
    table: FromABC
    on_statement: Any = attrs.field(converter=_convert_on_statement, default=None)
    lateral: bool = attrs.field(validator=attrs.validators.in_({True, False}), default=False)

    @on_statement.validator
    def _vld_on_statement(self, attribute, value):
        if self.type == 'cross':
            if value is not None:
                raise ValueError(value)
        elif value is None:
            raise ValueError('ON statement is required for %s join' % self.type)

    @lateral.validator
    def _vld_lateral(self, attribute, value):
        if value and self.type in {'right', 'full'}:
            raise ValueError('LATERAL is not allowed with %s join' % self.type)

    def _build(self, params: list | dict):
        sql = _JOIN_SQL[self.type]

        cte = self.table in CTX_CTE.get()
        if self.lateral:
            if cte:
                raise ValueError
            sql = '%s LATERAL' % sql

        res = '%s %s' % (
            sql,
            self.table._get_name() if cte else self.table._get_from_statement(params),
        )
        if self.on_statement is not None:
            with set_context({CTX_TABLES: ()}):  # should always prefix column with table name
                res += ' ON %s' % self.on_statement._build(params)

        return res


@attrs.frozen
class _UnionBase:
    select: Select
    expr: str

    def _build(self, params: list | dict) -> str:
        return '%s %s' % (self.expr, self.select._build(params))


@attrs.frozen
class _UnionUnique(_UnionBase):
    expr: str = 'UNION'


@attrs.frozen
class _UnionALL(_UnionBase):
    expr: str = 'UNION ALL'


@attrs.frozen
class _Intersect(_UnionBase):
    expr: str = 'INTERSECT'


@attrs.frozen
class _Except(_UnionBase):
    expr: str = 'EXCEPT'


def _convert_locking_of(value):
    if value is not None and not isinstance(value, tuple):
        value = tuple(value) if isinstance(value, (list, set, frozenset)) else (value,)
    return value


_LOCK_STRENGTHS: Final = frozenset({
    'UPDATE', 'NO KEY UPDATE', 'SHARE', 'KEY SHARE',
})


@attrs.frozen
class _Locking:
    strength: str = attrs.field(
        validator=attrs.validators.in_(_LOCK_STRENGTHS),
        default='UPDATE',
    )
    of: tuple[FromABC, ...] | None = attrs.field(converter=_convert_locking_of, default=None)
    nowait: bool = attrs.field(validator=attrs.validators.in_({True, False}), default=False)
    skip_locked: bool = attrs.field(
        validator=attrs.validators.in_({True, False}),
        default=False,
    )

    @of.validator
    def _vld_of(self, attribute, value):
        if (
            value is not None
            and (bad := next((i for i in value if not isinstance(i, FromABC)), None)) is not None
        ):
            raise TypeError(bad)

    @skip_locked.validator
    def _vld_skip_locked(self, attribute, value):
        if value and self.nowait:
            raise ValueError('NOWAIT and SKIP LOCKED are mutually exclusive')

    def _build(self) -> str:
        res = 'FOR %s' % self.strength
        if self.of:
            res = '%s OF %s' % (res, ', '.join(i._get_name() for i in self.of))
        if self.nowait:
            res = '%s NOWAIT' % res
        if self.skip_locked:
            res = '%s SKIP LOCKED' % res
        return res


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
    _with_recursive: bool = attrs.field(alias='x_with_recursive', default=False)
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
    _union: tuple[_UnionBase, ...] = attrs.field(alias='x_union', factory=tuple)
    _locking: _Locking | None = attrs.field(alias='x_locking', default=None)
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
        if (bad := next((i for i in value if not isinstance(i, CompileABC)), None)) is not None:
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
            x_join=self._join + (_Join('inner', other, on_statement=on_statement),),
        )

    def LeftJoin(self, other: FromABC, on_statement):
        return attrs.evolve(
            self,
            x_join=self._join + (_Join('left', other, on_statement=on_statement),),
        )

    def RightJoin(self, other: FromABC, on_statement):
        return attrs.evolve(
            self,
            x_join=self._join + (_Join('right', other, on_statement=on_statement),),
        )

    def FullJoin(self, other: FromABC, on_statement):
        return attrs.evolve(
            self,
            x_join=self._join + (_Join('full', other, on_statement=on_statement),),
        )

    def CrossJoin(self, other: FromABC):
        return attrs.evolve(self, x_join=self._join + (_Join('cross', other),))

    def JoinLateral(self, other: FromABC, on_statement):
        return attrs.evolve(
            self,
            x_join=self._join + (_Join('inner', other, on_statement=on_statement, lateral=True),),
        )

    def LeftJoinLateral(self, other: FromABC, on_statement):
        return attrs.evolve(
            self,
            x_join=self._join + (_Join('left', other, on_statement=on_statement, lateral=True),),
        )

    def CrossJoinLateral(self, other: FromABC):
        return attrs.evolve(self, x_join=self._join + (_Join('cross', other, lateral=True),))

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
        return attrs.evolve(self, x_union=self._union + (_UnionUnique(other),))

    def UnionAll(self, other: Select):
        return attrs.evolve(self, x_union=self._union + (_UnionALL(other),))

    def Intersect(self, other: Select):
        return attrs.evolve(self, x_union=self._union + (_Intersect(other),))

    def Except(self, other: Select):
        return attrs.evolve(self, x_union=self._union + (_Except(other),))

    def _lock(self, strength: str, of, nowait: bool, skip_locked: bool):
        return attrs.evolve(
            self,
            x_locking=_Locking(strength=strength, of=of, nowait=nowait, skip_locked=skip_locked),
        )

    def ForUpdate(self, *, of=None, nowait: bool = False, skip_locked: bool = False):
        return self._lock('UPDATE', of, nowait, skip_locked)

    def ForNoKeyUpdate(self, *, of=None, nowait: bool = False, skip_locked: bool = False):
        return self._lock('NO KEY UPDATE', of, nowait, skip_locked)

    def ForShare(self, *, of=None, nowait: bool = False, skip_locked: bool = False):
        return self._lock('SHARE', of, nowait, skip_locked)

    def ForKeyShare(self, *, of=None, nowait: bool = False, skip_locked: bool = False):
        return self._lock('KEY SHARE', of, nowait, skip_locked)

    def As(self, alias: str):
        return attrs.evolve(self, x_alias=alias)

    def Cast(self, to: str):
        return attrs.evolve(self, x_cast=to)

    def Subquery(self, alias: str, materialized: bool = False):
        return Subquery(self, alias=alias, materialized=materialized)

    def _build(self, params: list | dict) -> str:
        parts = []

        if self._with:
            if CTX_CTE.get():
                raise ValueError
            CTX_CTE.set(self._with)
            parts.append(build_with(self._with, params, recursive=self._with_recursive))

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

        if self._locking is not None:
            parts.append(self._locking._build())

        res = ' '.join(parts)

        if self._cast is not None:
            res = build_cast(res, cast=self._cast)

        if self._alias is not None:
            res = '(%s) AS %s' % (res, self._alias)

        return res
