from contextvars import copy_context

import attrs

from .array import Array
from .case import Case
from .column import Excluded
from .delete import Delete
from .func import F, Func
from .insert import Insert
from .literal import NULL, Literal
from .operators import And, Exists, Not, Or
from .param import Param
from .select import Select
from .subquery import Subquery
from .table import Table
from .update import Update
from .utils import (
    CTX_ALIAS_ONLY,
    CTX_CTE,
    CTX_DISABLE_TABLE_IN_COLUMN,
    CTX_FORCE_CAST_BRACKETS,
    CTX_TABLES,
    CompileABC,
)


__version__ = '0.1.4'
__all__ = (
    'And',
    'Array',
    'Case',
    'Delete',
    'Excluded',
    'Exists',
    'F',
    'Func',
    'Insert',
    'Literal',
    'Not',
    'NULL',
    'Param',
    'Or',
    'Select',
    'Table',
    'Update',
    'With',
    'build',
)


@attrs.frozen(init=False)
class With:
    _subqueries: tuple[Subquery, ...] = attrs.field(alias='subqueries')

    @_subqueries.validator
    def _vld_subqueries(self, attribute, value):
        if not value:
            raise ValueError
        elif bad := [i for i in value if not isinstance(i, Subquery)]:
            raise TypeError(bad)

    def __init__(self, *subqueries: Subquery):
        self.__attrs_init__(subqueries)

    def Select(self, *columns) -> Select:
        return Select(*columns, x_with=self._subqueries)

    def Insert(self, table: Table, columns: tuple) -> Insert:
        return Insert(table, columns=columns, x_with=self._subqueries)

    def Update(self, table: Table) -> Update:
        return Update(table, x_with=self._subqueries)

    def Delete(self, table: Table) -> Delete:
        return Delete(table, x_with=self._subqueries)


def build(item: CompileABC) -> tuple[str | None, list]:
    def run():
        CTX_FORCE_CAST_BRACKETS.set(False)
        CTX_CTE.set(())
        CTX_TABLES.set(())
        CTX_ALIAS_ONLY.set(False)
        CTX_DISABLE_TABLE_IN_COLUMN.set(False)
        return item._build(params := []), params

    return copy_context().run(run)
