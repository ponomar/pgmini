import attrs

from .column import prepare_column
from .subquery import Subquery
from .table import Table
from .utils import CTX_CTE, CompileABC, build_returning, build_where, build_with


def _convert_returning(value):
    return tuple(prepare_column(i) for i in value)


@attrs.frozen
class Delete(CompileABC):
    _table: Table = attrs.field(alias='table')
    _with: tuple[Subquery, ...] = attrs.field(alias='x_with', factory=tuple)
    _where: tuple[CompileABC, ...] = attrs.field(alias='x_where', factory=tuple)
    _returning: tuple[CompileABC, ...] = attrs.field(alias='x_returning', factory=tuple)

    def Where(self, *statements: CompileABC):
        """New statements will be added to old ones"""
        return attrs.evolve(self, x_where=self._where + statements)

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

        parts.append('DELETE FROM %s' % self._table._name)
        if self._where:
            parts.append(build_where(self._where, params=params))
        if self._returning:
            parts.append(build_returning(self._returning, params=params))

        return ' '.join(parts)
