from typing import Any

import attrs

from .column import Column, prepare_column
from .select import Select
from .subquery import Subquery
from .table import Table
from .utils import (
    CTX_CTE,
    CTX_DISABLE_TABLE_IN_COLUMN,
    CTX_FORCE_CAST_BRACKETS,
    RE_FUNC_PARENTHESIZED,
    RE_NEED_BRACKETS,
    RE_PARENTHESIZED,
    CompileABC,
    build_returning,
    build_set,
    build_with,
    set_context,
)


def _convert_do_update(value):
    if value is not None:
        return {k: prepare_column(v) for k, v in value.items()}


def _wrap_index_elements_with_brackets(value: str) -> str:
    if (
        RE_NEED_BRACKETS.search(value)
        and not RE_PARENTHESIZED.fullmatch(value)
        and not RE_FUNC_PARENTHESIZED.fullmatch(value)
    ):
        value = '(%s)' % value
    return value


@attrs.frozen(kw_only=True)
class OnConflict:
    constraint: str | None = None
    index_elements: tuple[str | CompileABC, ...] | None = None
    index_where: CompileABC | None = attrs.field(default=None)
    do_update: dict[str | Column, Any] | None = attrs.field(
        converter=_convert_do_update,
        default=None,
    )
    do_nothing: bool = attrs.field(validator=attrs.validators.in_({True, False}), default=False)

    @index_where.validator
    def _vld_index(self, attribute, value):
        if self.constraint is not None:
            if not (self.index_elements is None and self.index_where is None):
                raise ValueError((self.index_elements, self.index_where))
        elif self.index_elements is None and self.index_where is not None:
            raise ValueError(self.index_where)

    @do_nothing.validator
    def _vld_do(self, attribute, value):
        if self.do_update is not None:
            if self.do_nothing:
                raise ValueError
        elif not self.do_nothing:
            raise ValueError('do_update or do_nothing must be specified')

    def build(self, params: list) -> str:
        res = ['ON CONFLICT']
        if self.constraint is not None:
            res.append('ON CONSTRAINT %s' % self.constraint)

        if self.index_elements is not None:
            with set_context({
                CTX_FORCE_CAST_BRACKETS: True,
                CTX_DISABLE_TABLE_IN_COLUMN: True,
            }):
                res.append('(%s)' % ', '.join(
                    _wrap_index_elements_with_brackets(
                        i._build(params)
                        if isinstance(i, CompileABC)
                        else i
                    )
                    for i in self.index_elements
                ))

        if self.index_where is not None:
            with set_context({CTX_DISABLE_TABLE_IN_COLUMN: True}):
                res.append('WHERE %s' % self.index_where._build(params))

        if self.do_update is not None:
            res.append(
                'DO UPDATE %s'
                % build_set(self.do_update, params=params)
            )

        if self.do_nothing:
            res.append('DO NOTHING')

        return ' '.join(res)


def _convert_returning(value):
    return tuple(prepare_column(i) for i in value)


def _convert_values(value):
    return tuple(
        [prepare_column(item) for item in row]
        for row in value
    )


@attrs.frozen
class Insert(CompileABC):
    _table: Table = attrs.field(alias='table')
    _columns: tuple[str | Column, ...] = attrs.field(alias='columns')
    _with: tuple[Subquery, ...] = attrs.field(alias='x_with', factory=tuple)
    _values: tuple[tuple, ...] = attrs.field(
        alias='x_values',
        converter=_convert_values,
        factory=tuple,
    )
    _select: Select | None = attrs.field(alias='x_select', default=None)
    _on_conflict: OnConflict | None = attrs.field(alias='x_on_conflict', default=None)
    _returning: tuple[CompileABC, ...] = attrs.field(
        alias='x_returning',
        converter=_convert_returning,
        factory=tuple,
    )

    @_columns.validator
    def _vld_columns(self, attribute, value):
        if not value:
            raise ValueError

    @_select.validator
    def _vld_select(self, attribute, value):
        if self._select is not None and self._values != ():
            raise ValueError(self._values)

    @_values.validator
    def _vld_values(self, attribute, value):
        if self._values:
            if self._select is not None:
                raise ValueError(self._select)
            for row in self._values:
                if len(row) != len(self._columns):
                    raise ValueError((len(row), len(self._columns)))
                elif bad := [i for i in row if not isinstance(i, CompileABC)]:
                    raise TypeError(bad)

    def Values(self, *rows: tuple):
        return attrs.evolve(self, x_values=rows)

    def Select(self, select: Select):
        return attrs.evolve(self, x_select=select)

    def OnConflict(
        self, *,
        constraint: str | None = None,
        index_elements: tuple[str | Column, ...] | None = None,
        index_where: CompileABC | None = None,
        do_update: dict | None = None,
        do_nothing: bool = False,
    ):
        return attrs.evolve(self, x_on_conflict=OnConflict(
            constraint=constraint,
            index_elements=index_elements,
            index_where=index_where,
            do_update=do_update,
            do_nothing=do_nothing,
        ))

    def Returning(self, *columns):
        return attrs.evolve(self, x_returning=columns)

    def Subquery(self, alias: str, materialized: bool = False) -> Subquery:
        return Subquery(self, alias=alias, materialized=materialized)

    def _build(self, params: list) -> str:
        parts = []
        if self._with:
            if CTX_CTE.get():
                raise ValueError
            CTX_CTE.set(self._with)
            parts.append(build_with(self._with, params))

        with set_context({CTX_DISABLE_TABLE_IN_COLUMN: True}):
            parts.append('INSERT INTO %s (%s)' % (
                self._table._get_from_statement(params),
                ', '.join(
                    col._build(params) if isinstance(col, Column) else col
                    for col in self._columns
                ),
            ))

        if self._values:
            parts.append('VALUES %s' % ', '.join(
                '(%s)' % ', '.join(i._build(params) for i in row)
                for row in self._values
            ))

        if self._select is not None:
            parts.append(self._select._build(params))
        if self._on_conflict is not None:
            parts.append(self._on_conflict.build(params))
        if self._returning:
            parts.append(build_returning(self._returning, params=params))

        return ' '.join(parts)
