import re
from abc import ABC, abstractmethod
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Final, Pattern


class SelectMX:
    pass


class CompileABC(ABC):
    @abstractmethod
    def _build(self, params: list) -> str | None:
        raise NotImplementedError


class FromABC(ABC):
    @abstractmethod
    def _get_from_statement(self, params: list) -> str:
        raise NotImplementedError

    @abstractmethod
    def _get_name(self) -> str:
        raise NotImplementedError


RE_NEED_BRACKETS: Final[Pattern] = re.compile("[^a-z0-9$._']", flags=re.IGNORECASE)
RE_PARENTHESIZED: Final[Pattern] = re.compile(r'\(.*\)')
RE_FUNC_PARENTHESIZED: Final[Pattern] = re.compile(r'[a-z0-9_.]+\([^()]*\)', flags=re.IGNORECASE)
RE_SINGLE_QUOTED: Final[Pattern] = re.compile("'[^']*'")
RE_ARRAY: Final[Pattern] = re.compile(r'ARRAY\[.*\]')
ITERABLES: Final[tuple] = (list, tuple, set, frozenset)
STAR_SIGN: Final[str] = '*'
CTX_FORCE_CAST_BRACKETS: Final[ContextVar[bool]] = ContextVar('force_cast_brackets')
CTX_CTE: Final[ContextVar[tuple]] = ContextVar('cte')
CTX_DISABLE_TABLE_IN_COLUMN: Final[ContextVar[bool]] = ContextVar('disable_table_in_column')
CTX_TABLES: Final[ContextVar[tuple[FromABC, ...]]] = ContextVar('tables')
CTX_ALIAS_ONLY: Final[ContextVar[bool]] = ContextVar('alias_only')


@contextmanager
def set_context(items: dict[ContextVar, Any]):
    tokens = {ctx: ctx.set(value) for ctx, value in items.items()}

    yield

    for ctx, token in tokens.items():
        ctx.reset(token)


def build_where(statements, params: list) -> str:
    from .operators import And

    if len(statements) > 1:
        statement = And(*statements)
    else:
        statement = statements[0]
    return 'WHERE %s' % statement._build(params)


def wrap_brackets_if_needed(item: str, obj) -> str:
    from .select import Select
    if isinstance(obj, Select) and obj._cast is None and obj._alias is None:
        item = '(%s)' % item
    return item


def build_with(statements, params: list) -> str:
    return 'WITH %s' % ', '.join(i._get_with_statement(params) for i in statements)


def build_from(statements, params: list) -> str:
    return 'FROM %s' % ', '.join(
        i._alias if i in CTX_CTE.get() else i._get_from_statement(params)
        for i in statements
    )


def build_returning(columns, params: list) -> str:
    return 'RETURNING %s' % ', '.join(i._build(params) for i in columns)


def build_set(items: dict, params: list) -> str:
    parts = []
    for k, v in items.items():
        if isinstance(k, CompileABC):
            with set_context({CTX_DISABLE_TABLE_IN_COLUMN: True}):
                col = k._build(params)
        else:
            col = k
        parts.append('%s = %s' % (col, v._build(params)))

    return 'SET %s' % ', '.join(parts)
