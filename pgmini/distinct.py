import attrs

from .marks import Marks


class DistinctMX:
    def Distinct(self):
        if self._marks:
            marks = attrs.evolve(self._marks, distinct=True)
        else:
            marks = Marks(distinct=True)
        return attrs.evolve(self, x_marks=marks)
