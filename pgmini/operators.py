import attrs

from .alias import AliasMX, extract_alias
from .cast import CastMX
from .distinct import DistinctMX
from .marks import MARKS_FIELD, MARKS_TYPE
from .operation import OperationMX
from .order_by import OrderByMX
from .utils import CompileABC, SelectMX


@attrs.frozen(eq=False, repr=False, init=False)
class And(CompileABC, CastMX, AliasMX, DistinctMX, OrderByMX, OperationMX, SelectMX):
    _statements: tuple[CompileABC, ...] = attrs.field(alias='statements')
    _marks: MARKS_TYPE = MARKS_FIELD
    _sql: str = 'AND'

    @_statements.validator
    def _vld_statements(self, attribute, value):
        if not all(i is not None for i in value):
            raise ValueError(value)

    def __init__(self, *statements: CompileABC, **kwargs):
        kwargs.setdefault('statements', statements)
        self.__attrs_init__(**kwargs)

    def _build(self, params: list) -> str | None:
        if not self._statements:
            return
        elif alias := extract_alias(self):
            return alias

        if len(self._statements) == 1:
            res = self._statements[0]._build(params)
        else:
            res = (' %s ' % self._sql).join(
                '(%s)' % j if isinstance(i, Or) else j for i in self._statements
                if (j := i._build(params)) is not None
            )

        if self._marks:
            res = self._marks.build(res)
        return res

    def __repr__(self):
        res = '%s(%s)' % (self.__class__.__name__, ', '.join(repr(i) for i in self._statements))
        if self._marks:
            res += f':{repr(self._marks)}'
        return res


@attrs.frozen(eq=False, repr=False, init=False)
class Or(And):
    _sql: str = 'OR'


@attrs.frozen(eq=False, repr=False)
class Not(CompileABC, CastMX, AliasMX, DistinctMX, OrderByMX, OperationMX, SelectMX):
    _statement: CompileABC = attrs.field(alias='statement')
    _marks: MARKS_TYPE = MARKS_FIELD

    def _build(self, params: list) -> str:
        from .operations import Operation

        if alias := extract_alias(self):
            return alias

        if isinstance(self._statement, Operation):
            expr = 'NOT %s'
        else:
            expr = 'NOT (%s)'
        res = expr % self._statement._build(params)
        if self._marks:
            res = self._marks.build(res)
        return res

    def __repr__(self):
        res = '%s(%s)' % (self.__class__.__name__, repr(self._statement))
        if self._marks:
            res += f':{repr(self._marks)}'
        return res


@attrs.frozen(eq=False, repr=False)
class Exists(Not):
    def _build(self, params: list) -> str:
        if alias := extract_alias(self):
            return alias

        res = 'EXISTS (%s)' % self._statement._build(params)
        if self._marks:
            res = self._marks.build(res)
        return res
