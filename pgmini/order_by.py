from typing import TypeVar

import attrs

from .marks import Marks
from .utils import CompileABC


class OrderByMX:
    def Desc(self):
        if self._marks:
            marks = attrs.evolve(self._marks, order_by='DESC')
        else:
            marks = Marks(order_by='DESC')
        return attrs.evolve(self, x_marks=marks)

    def Asc(self):
        if self._marks:
            marks = attrs.evolve(self._marks, order_by='ASC')
        else:
            marks = Marks(order_by='DESC')
        return attrs.evolve(self, x_marks=marks)

    def NullsFirst(self):
        if self._marks:
            marks = attrs.evolve(self._marks, order_by_nulls='FIRST')
        else:
            marks = Marks(order_by_nulls='FIRST')
        return attrs.evolve(self, x_marks=marks)

    def NullsLast(self):
        if self._marks:
            marks = attrs.evolve(self._marks, order_by_nulls='LAST')
        else:
            marks = Marks(order_by_nulls='LAST')
        return attrs.evolve(self, x_marks=marks)


def build_order_by(value: str, marks: Marks) -> str:
    if marks.order_by:
        value = '%s %s' % (value, marks.order_by)
    if marks.order_by_nulls:
        value = '%s NULLS %s' % (value, marks.order_by_nulls)
    return value


_Object = TypeVar('_Object')


def do_order_by(obj: _Object, statements: tuple[CompileABC, ...]) -> _Object:
    if len(statements) == 1 and statements[0] is None:
        value = ()
    else:
        if any(i is None for i in statements):
            raise ValueError(statements)
        value = obj._order_by + statements

    return attrs.evolve(obj, x_order_by=value)
