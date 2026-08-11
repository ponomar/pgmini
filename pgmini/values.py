import attrs

from .column import Column, prepare_column
from .utils import STAR_SIGN, FromABC


def _convert_rows(value):
    return tuple(
        tuple(prepare_column(item) for item in row)
        for row in value
    )


@attrs.frozen(eq=False, init=False)
class Values(FromABC):
    _rows: tuple[tuple[Column, ...], ...] = attrs.field(alias='rows', converter=_convert_rows)
    _alias: str | None = attrs.field(alias='x_alias', default=None)

    def __init__(self, *rows, **kwargs):
        kwargs.setdefault('rows', rows)
        self.__attrs_init__(**kwargs)

    @_rows.validator
    def _vld_rows(self, attribute, value):
        if not value:
            raise ValueError
        elif len({len(row) for row in value}) > 1:
            raise ValueError('all rows must have the same length')

    def As(self, alias: str):
        return attrs.evolve(self, x_alias=alias)

    @property
    def STAR(self) -> Column:
        return Column(STAR_SIGN, table=self)

    def __getattribute__(self, item: str) -> Column:
        try:
            return object.__getattribute__(self, item)
        except AttributeError:
            return Column(item, table=self)

    def _get_from_statement(self, params: list) -> str:
        res = '(VALUES %s)' % ', '.join(
            '(%s)' % ', '.join(i._build(params) for i in row)
            for row in self._rows
        )
        if self._alias is not None:
            res = '%s AS %s' % (res, self._alias)
        return res

    def _get_name(self) -> str:
        if self._alias is None:
            raise ValueError('Values requires an alias: Values(...).As("v(col1, col2)")')
        # 'v(a, b)' -> 'v'
        return self._alias.split('(', 1)[0].strip()

    def __hash__(self):
        return id(self)
