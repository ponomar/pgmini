from typing import Any

import attrs

from .column import Column, prepare_column
from .subquery import Subquery
from .table import Table
from .utils import (
    CTX_CTE,
    CompileABC,
    FromABC,
    build_from,
    build_returning,
    build_set,
    build_where,
    build_with,
)


def _convert_set(value):
    if value:
        return {k: prepare_column(v) for k, v in value.items()}


def _convert_returning(value):
    return tuple(prepare_column(i) for i in value)


@attrs.frozen
class Update(CompileABC):
    _table: Table = attrs.field(alias='table')
    _with: tuple[Subquery, ...] = attrs.field(alias='x_with', factory=tuple)
    _set: dict[str | Column, CompileABC] | None = attrs.field(
        alias='x_set',
        converter=_convert_set,
        default=None,
    )
    _from: tuple[FromABC, ...] = attrs.field(alias='x_from', factory=tuple)
    _where: tuple[CompileABC, ...] = attrs.field(alias='x_where', factory=tuple)
    _returning: tuple[CompileABC, ...] = attrs.field(
        alias='x_returning',
        converter=_convert_returning,
        factory=tuple,
    )

    @_from.validator
    def _vld_from(self, attribute, value):
        if bad := [i for i in value if not isinstance(i, FromABC)]:
            raise TypeError(bad)

    def Set(self, items: dict[str | Column, Any]):
        return attrs.evolve(self, x_set=items)

    def From(self, *froms):
        return attrs.evolve(self, x_from=froms)

    def Where(self, *statements: CompileABC):
        """New statements will be added to old ones"""
        return attrs.evolve(self, x_where=self._where + statements)

    def Returning(self, *columns):
        return attrs.evolve(self, x_returning=columns)

    def Subquery(self, alias: str, materialized: bool = False) -> Subquery:
        return Subquery(self, alias=alias, materialized=materialized)

    def _build(self, params: list) -> str:
        if not self._set:
            raise ValueError

        parts = []
        if self._with:
            if CTX_CTE.get():
                raise ValueError
            CTX_CTE.set(self._with)
            parts.append(build_with(self._with, params))

        parts.extend([
            'UPDATE %s' % self._table._name,
            build_set(self._set, params=params),
        ])
        if self._from:
            parts.append(build_from(self._from, params))
        if self._where:
            parts.append(build_where(self._where, params=params))
        if self._returning:
            parts.append(build_returning(self._returning, params=params))

        return ' '.join(parts)
