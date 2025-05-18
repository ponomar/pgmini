import attrs

from .marks import Marks
from .utils import (
    CTX_FORCE_CAST_BRACKETS,
    RE_ARRAY,
    RE_FUNC_PARENTHESIZED,
    RE_NEED_BRACKETS,
    RE_PSYCOPG_PARAM,
    RE_SINGLE_QUOTED,
    is_fully_enclosed_in_brackets,
)


class CastMX:
    def Cast(self, to: str):
        if self._marks:
            marks = attrs.evolve(self._marks, cast=to)
        else:
            marks = Marks(cast=to)
        return attrs.evolve(self, x_marks=marks)


def build_cast(value: str, cast: str) -> str:
    if (
        RE_NEED_BRACKETS.search(value)
        and not is_fully_enclosed_in_brackets(value)
        and not RE_FUNC_PARENTHESIZED.fullmatch(value)
        and not RE_SINGLE_QUOTED.fullmatch(value)
        and not RE_ARRAY.fullmatch(value)
        and not RE_PSYCOPG_PARAM.fullmatch(value)
    ):
        value = '(%s)' % value
    value = '%s::%s' % (value, cast)
    if CTX_FORCE_CAST_BRACKETS.get():
        value = '(%s)' % value
    return value
