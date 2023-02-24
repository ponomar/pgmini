import attrs

from .column import Column
from .utils import STAR_SIGN, CompileABC, FromABC


def _convert_statement(value):
    from .select import Select

    if isinstance(value, Select) and (value._cast is not None or value._alias is not None):
        value = attrs.evolve(value, x_cast=None, x_alias=None)
    return value


@attrs.frozen
class Subquery(FromABC):
    _statement: CompileABC = attrs.field(alias='statement', converter=_convert_statement)
    _alias: str = attrs.field(alias='alias')
    _materialized: bool = attrs.field(
        alias='materialized',
        validator=attrs.validators.in_({True, False}),
        default=False,
    )

    @_alias.validator
    def _vld_alias(self, attribute, value):
        if not value:
            raise ValueError

    @property
    def STAR(self) -> Column:
        return Column(STAR_SIGN, table=self)

    def __getattribute__(self, item: str) -> Column:
        try:
            return object.__getattribute__(self, item)
        except AttributeError:
            return Column(item, table=self)

    def As(self, alias: str, materialized: bool = False):
        return attrs.evolve(self, alias=alias, materialized=materialized)

    def _get_from_statement(self, params: list) -> str:
        return '(%s) AS %s' % (self._statement._build(params), self._alias)

    def _get_name(self) -> str:
        return self._alias

    def _get_with_statement(self, params: list) -> str:
        res = '%s AS' % self._alias
        if self._materialized:
            res = '%s MATERIALIZED' % res
        return '%s (%s)' % (res, self._statement._build(params))

    def _build(self, params: list) -> str:
        return self._get_from_statement(params)
