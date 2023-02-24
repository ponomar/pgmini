from typing import Literal as LiteralT, TypeAlias

import attrs


@attrs.frozen(kw_only=True, repr=False)
class Marks:
    order_by: LiteralT['ASC', 'DESC'] | None = attrs.field(
        validator=attrs.validators.optional(attrs.validators.in_({'ASC', 'DESC'})),
        default=None,
    )
    order_by_nulls: LiteralT['FIRST', 'LAST'] | None = attrs.field(
        validator=attrs.validators.optional(attrs.validators.in_({'FIRST', 'LAST'})),
        default=None,
    )
    cast: str | None = attrs.field(default=None)
    alias: str | None = attrs.field(default=None)
    distinct: bool = attrs.field(validator=attrs.validators.in_({True, False}), default=False)

    @distinct.validator
    def _vld_distinct(self, attribute, value):
        if not isinstance(value, bool):
            raise TypeError(value)

    def __bool__(self):
        return (
            self.order_by is not None
            or self.order_by_nulls is not None
            or self.cast is not None
            or self.alias is not None
            or self.distinct
        )

    def build(self, value: str) -> str:
        from .cast import build_cast
        from .order_by import build_order_by

        if self.cast:
            value = build_cast(value, cast=self.cast)
        if self.alias:
            value = '%s AS %s' % (value, self.alias)
        if self.distinct:
            value = 'DISTINCT %s' % value
        return build_order_by(value, marks=self)

    def __repr__(self):
        items = []
        if self.order_by:
            items.append(f'order_by={self.order_by}')
        if self.order_by_nulls:
            items.append(f'nulls={self.order_by_nulls}')
        if self.cast:
            items.append(f'cast={self.cast}')
        if self.alias:
            items.append(f'alias={self.alias}')
        if self.distinct:
            items.append('distinct=true')
        return 'Marks(%s)' % ', '.join(items)


MARKS_TYPE: TypeAlias = Marks | None
MARKS_FIELD = attrs.field(alias='x_marks', default=None)
