from typing import Any

import attrs

from .column import Column, prepare_column
from .literal import Literal
from .subquery import Subquery
from .table import Table
from .utils import (
    CTX_CTE,
    CTX_DISABLE_TABLE_IN_COLUMN,
    CompileABC,
    FromABC,
    build_returning,
    build_set,
    build_with,
    set_context,
)


def _convert_on_statement(value):
    if value is True:
        value = Literal(True)
    return value


def _convert_set(value):
    if value is not None:
        return {k: prepare_column(v) for k, v in value.items()}


def _convert_values(value):
    if value is not None:
        return tuple(prepare_column(i) for i in value)


@attrs.frozen(kw_only=True)
class _When:
    matched: bool = attrs.field(validator=attrs.validators.in_({True, False}))
    action: str = attrs.field(
        validator=attrs.validators.in_({'update', 'delete', 'insert', 'nothing'}),
    )
    set: dict[str | Column, CompileABC] | None = attrs.field(converter=_convert_set, default=None)
    columns: tuple[str | Column, ...] | None = attrs.field(default=None)
    values: tuple[CompileABC, ...] | None = attrs.field(converter=_convert_values, default=None)
    condition: CompileABC | None = attrs.field(default=None)

    def _build(self, params: list | dict) -> str:
        res = 'WHEN MATCHED' if self.matched else 'WHEN NOT MATCHED'
        if self.condition is not None:
            res = '%s AND %s' % (res, self.condition._build(params))
        res = '%s THEN' % res

        if self.action == 'update':
            res = '%s UPDATE %s' % (res, build_set(self.set, params=params))
        elif self.action == 'delete':
            res = '%s DELETE' % res
        elif self.action == 'nothing':
            res = '%s DO NOTHING' % res
        else:
            with set_context({CTX_DISABLE_TABLE_IN_COLUMN: True}):
                cols = ', '.join(
                    col._build(params) if isinstance(col, Column) else col
                    for col in self.columns
                )
            res = '%s INSERT (%s) VALUES (%s)' % (
                res,
                cols,
                ', '.join(i._build(params) for i in self.values),
            )

        return res


@attrs.frozen
class Merge(CompileABC):
    _table: Table = attrs.field(alias='table')
    _with: tuple[Subquery, ...] = attrs.field(alias='x_with', factory=tuple)
    _with_recursive: bool = attrs.field(alias='x_with_recursive', default=False)
    _using: FromABC | None = attrs.field(alias='x_using', default=None)
    _on: CompileABC | None = attrs.field(
        alias='x_on',
        converter=_convert_on_statement,
        default=None,
    )
    _whens: tuple[_When, ...] = attrs.field(alias='x_whens', factory=tuple)
    _returning: tuple[CompileABC, ...] = attrs.field(alias='x_returning', factory=tuple)

    def Using(self, other: FromABC, on_statement):
        if not isinstance(other, FromABC):
            raise TypeError(other)
        return attrs.evolve(self, x_using=other, x_on=on_statement)

    def _when(self, **kwargs):
        return attrs.evolve(self, x_whens=self._whens + (_When(**kwargs),))

    def WhenMatchedUpdate(self, items: dict[str | Column, Any], condition=None):
        return self._when(matched=True, action='update', set=items, condition=condition)

    def WhenMatchedDelete(self, condition=None):
        return self._when(matched=True, action='delete', condition=condition)

    def WhenMatchedDoNothing(self, condition=None):
        return self._when(matched=True, action='nothing', condition=condition)

    def WhenNotMatchedInsert(self, columns, values, condition=None):
        return self._when(
            matched=False,
            action='insert',
            columns=tuple(columns),
            values=tuple(values),
            condition=condition,
        )

    def WhenNotMatchedDoNothing(self, condition=None):
        return self._when(matched=False, action='nothing', condition=condition)

    def Returning(self, *columns):
        return attrs.evolve(
            self,
            x_returning=tuple(prepare_column(i) for i in columns),
        )

    def Subquery(self, alias: str, materialized: bool = False) -> Subquery:
        return Subquery(self, alias=alias, materialized=materialized)

    def _build(self, params: list | dict) -> str:
        if self._using is None or self._on is None:
            raise ValueError('Using() is required')
        elif not self._whens:
            raise ValueError('at least one WHEN clause is required')

        parts = []
        if self._with:
            if CTX_CTE.get():
                raise ValueError
            CTX_CTE.set(self._with)
            parts.append(build_with(self._with, params, recursive=self._with_recursive))

        cte = self._using in CTX_CTE.get()
        parts.append('MERGE INTO %s USING %s ON %s' % (
            self._table._get_from_statement(params),
            self._using._get_name() if cte else self._using._get_from_statement(params),
            self._on._build(params),
        ))
        parts.extend(obj._build(params) for obj in self._whens)

        if self._returning:
            parts.append(build_returning(self._returning, params=params))

        return ' '.join(parts)
