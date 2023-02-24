class OperationMX:
    def __eq__(self, other):
        from .operations import OperationEquality
        return OperationEquality(self, right=other, operator_eq='=', operator_is='IS')

    def __ne__(self, other):
        from .operations import OperationEquality
        return OperationEquality(self, right=other, operator_eq='!=', operator_is='IS NOT')

    def __gt__(self, other):
        from .operations import OperationMath
        return OperationMath(self, right=other, operator='>')

    def __ge__(self, other):
        from .operations import OperationMath
        return OperationMath(self, right=other, operator='>=')

    def __lt__(self, other):
        from .operations import OperationMath
        return OperationMath(self, right=other, operator='<')

    def __le__(self, other):
        from .operations import OperationMath
        return OperationMath(self, right=other, operator='<=')

    def __add__(self, other):
        from .operations import OperationMath
        return OperationMath(self, right=other, operator='+')

    def __sub__(self, other):
        from .operations import OperationMath
        return OperationMath(self, right=other, operator='-')

    def __mul__(self, other):
        from .operations import OperationMath
        return OperationMath(self, right=other, operator='*')

    def __truediv__(self, other):
        from .operations import OperationMath
        return OperationMath(self, right=other, operator='/')

    def Is(self, other):
        from .operations import OperationMath
        return OperationMath(self, right=other, operator='IS')

    def IsNot(self, other):
        from .operations import OperationMath
        return OperationMath(self, right=other, operator='IS NOT')

    def In(self, other):
        from .operations import OperationIn
        return OperationIn(self, items=other)

    def NotIn(self, other):
        from .operations import OperationIn
        return OperationIn(self, items=other, operator='NOT IN')

    def Any(self, other):
        from .operations import OperationAny
        return OperationAny(self, right=other)

    def Between(self, start, end):
        from .operations import OperationBetween
        return OperationBetween(self, start=start, end=end)

    def Like(self, other):
        from .operations import OperationLike
        return OperationLike(self, right=other)

    def Ilike(self, other):
        from .operations import OperationLike
        return OperationLike(self, right=other, operator='ILIKE')

    def Op(self, operator: str, other):
        from .operations import OperationCustom
        return OperationCustom(self, operator=operator, right=other)
