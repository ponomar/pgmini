import attrs

from .alias import AliasMX, extract_alias
from .cast import CastMX
from .distinct import DistinctMX
from .marks import MARKS_FIELD, MARKS_TYPE
from .operation import OperationMX
from .order_by import OrderByMX
from .param import Param
from .utils import CTX_DISABLE_TABLE_IN_COLUMN, CTX_TABLES, CompileABC, FromABC, SelectMX


class _Excluded(FromABC):
    def _get_from_statement(self, params: list) -> str:
        raise RuntimeError

    def _get_name(self) -> str:
        return 'excluded'


@attrs.frozen(eq=False, unsafe_hash=True)
class Column(CompileABC, CastMX, AliasMX, DistinctMX, OrderByMX, OperationMX, SelectMX):
    _name: str = attrs.field(alias='name')
    _table: FromABC | None = attrs.field(alias='table', default=None)
    _marks: MARKS_TYPE = MARKS_FIELD

    def _build(self, params: list) -> str:
        if alias := extract_alias(self):
            return alias

        res = self._name
        if (
            not CTX_DISABLE_TABLE_IN_COLUMN.get()
            and (
                isinstance(self._table, _Excluded)
                or len(CTX_TABLES.get()) > 1
                or self._table not in CTX_TABLES.get()
            )
        ):
            res = f'{self._table._get_name()}.{res}'

        if self._marks:
            res = self._marks.build(res)
        return res


def Excluded(column: str | Column) -> Column:
    if isinstance(column, str):
        return Column(column, table=_Excluded())

    if not isinstance(column, Column):
        raise TypeError(column)

    return attrs.evolve(column, table=_Excluded())


def prepare_column(col):
    return col if isinstance(col, SelectMX) else Param(col)
