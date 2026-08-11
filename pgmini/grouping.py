import attrs

from .column import prepare_column
from .utils import ITERABLES, CompileABC, SelectMX


def _convert_sets(value):
    res = []
    for item in value:
        if isinstance(item, ITERABLES):
            res.append(tuple(prepare_column(i) for i in item))
        else:
            res.append((prepare_column(item),))
    return tuple(res)


@attrs.frozen(init=False)
class GroupingSets(CompileABC, SelectMX):
    _sets: tuple[tuple[CompileABC, ...], ...] = attrs.field(alias='sets', converter=_convert_sets)

    def __init__(self, *sets):
        self.__attrs_init__(sets)

    @_sets.validator
    def _vld_sets(self, attribute, value):
        if not value:
            raise ValueError

    def _build(self, params: list | dict) -> str:
        return 'GROUPING SETS (%s)' % ', '.join(
            '(%s)' % ', '.join(i._build(params) for i in item)
            for item in self._sets
        )
