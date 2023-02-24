from typing import Final

import attrs

from .column import Column
from .utils import STAR_SIGN, FromABC


_RESERVED: Final[frozenset[str]] = frozenset(['user', 'role'])


def _convert_name(value):
    if value in _RESERVED:
        value = '"%s"' % value
    return value


@attrs.frozen(eq=False)
class Table(FromABC):
    _name: str = attrs.field(alias='name', converter=_convert_name)
    _alias: str | None = attrs.field(alias='x_alias', default=None)

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
        res = self._name
        if self._alias is not None:
            res = '%s AS %s' % (res, self._alias)
        return res

    def _get_name(self) -> str:
        return self._alias or self._name

    def __hash__(self):
        return id(self)
