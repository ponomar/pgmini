import attrs

from .alias import AliasMX, extract_alias
from .cast import CastMX
from .distinct import DistinctMX
from .marks import MARKS_FIELD, MARKS_TYPE
from .operation import OperationMX
from .order_by import OrderByMX
from .param import Param
from .utils import CTX_DISABLE_TABLE_IN_COLUMN, CTX_TABLES, CompileABC, FromABC, SelectMX


@attrs.frozen
class _PseudoTable(FromABC):
    _name: str = attrs.field(alias='name')

    def _get_from_statement(self, params: list) -> str:
        raise RuntimeError

    def _get_name(self) -> str:
        return self._name


@attrs.frozen(eq=False, unsafe_hash=True)
class Column(CompileABC, CastMX, AliasMX, DistinctMX, OrderByMX, OperationMX, SelectMX):
    _name: str = attrs.field(alias='name')
    _table: FromABC | None = attrs.field(alias='table', default=None)
    _marks: MARKS_TYPE = MARKS_FIELD

    def _build(self, params: list | dict) -> str:
        if alias := extract_alias(self):
            return alias

        res = self._name
        if (
            not CTX_DISABLE_TABLE_IN_COLUMN.get()
            and self._table is not None
            and (
                isinstance(self._table, _PseudoTable)
                or len(CTX_TABLES.get()) > 1
                or self._table not in CTX_TABLES.get()
            )
        ):
            res = f'{self._table._get_name()}.{res}'

        if self._marks:
            res = self._marks.build(res)
        return res


def _pseudo_column(name: str, column: str | Column) -> Column:
    if isinstance(column, str):
        return Column(column, table=_PseudoTable(name))

    if not isinstance(column, Column):
        raise TypeError(column)

    return attrs.evolve(column, table=_PseudoTable(name))


def Excluded(column: str | Column) -> Column:
    return _pseudo_column('excluded', column)


def Old(column: str | Column) -> Column:
    """RETURNING old.<column> (PostgreSQL 18+)"""
    return _pseudo_column('old', column)


def New(column: str | Column) -> Column:
    """RETURNING new.<column> (PostgreSQL 18+)"""
    return _pseudo_column('new', column)


def prepare_column(col):
    return col if isinstance(col, SelectMX) else Param(col)
