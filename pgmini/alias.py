import attrs

from .marks import Marks
from .order_by import compile_order_by
from .utils import CTX_ALIAS_ONLY, CompileABC


class AliasMX:
    def As(self, alias: str):
        if self._marks:
            marks = attrs.evolve(self._marks, alias=alias)
        else:
            marks = Marks(alias=alias)
        return attrs.evolve(self, x_marks=marks)


def extract_alias(elem: CompileABC) -> str | None:
    if (
        CTX_ALIAS_ONLY.get()
        and (marks := getattr(elem, '_marks', None)) is not None
        and (alias := marks.alias) is not None
    ):
        return compile_order_by(alias, marks=marks)
