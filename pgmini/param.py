from copy import deepcopy
from typing import Any

import attrs

from .alias import AliasMX, extract_alias
from .cast import CastMX
from .distinct import DistinctMX
from .marks import MARKS_FIELD, MARKS_TYPE
from .operation import OperationMX
from .order_by import OrderByMX
from .utils import CompileABC, SelectMX


@attrs.frozen(repr=False, eq=False)
class Param(CompileABC, CastMX, AliasMX, DistinctMX, OrderByMX, OperationMX, SelectMX):
    _value: Any = attrs.field(alias='value', converter=deepcopy)
    _marks: MARKS_TYPE = MARKS_FIELD

    def _build(self, params: list) -> str:
        if alias := extract_alias(self):
            return alias

        index = len(params) + 1
        params.append(self._value)
        res = '$%d' % index
        if self._marks:
            res = self._marks.build(res)
        return res

    def __repr__(self):
        res = 'Param(%s)' % str(self._value)
        if self._marks:
            res += f':{repr(self._marks)}'
        return res

    def __hash__(self):
        return id(self)
