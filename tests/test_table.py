from functools import cache

from pgmini import Literal as L, Select as S, Table as T, build


def test():
    t = T('ololosh')

    c1 = t.some_col
    assert build(c1)[0] == 'ololosh.some_col'

    c2 = t.other.Cast('int').As('same_one')
    assert build(c2)[0] == 'ololosh.other::int AS same_one'

    c3 = t.STAR
    assert build(c3)[0] == 'ololosh.*'


def test_with_alias():
    t = T('table2').As('o')

    c1 = t.some_col
    assert build(c1)[0] == 'o.some_col'

    c2 = t.other.Cast('int').As('same_one')
    assert build(c2)[0] == 'o.other::int AS same_one'

    c3 = t.STAR
    assert build(c3)[0] == 'o.*'


def test_attributes_and_filters():
    class UserModel(T):
        id: int
        name: str
        email: str | None
        status: str | None

        @property
        @cache  # noqa: B019
        def status_active(self):
            return self.status == L('active')

    User = UserModel('users')
    Alias = User.As('u')
    Alias2 = Alias.As('u2')

    assert build(S(User.id).From(User).Where(User.status_active)) == (
        "SELECT id FROM users WHERE status = 'active'",
        [],
    )
    assert build(S(Alias.id).From(Alias).Where(Alias.status_active)) == (
        "SELECT id FROM users AS u WHERE status = 'active'",
        [],
    )
    assert build(S(Alias2.id).From(Alias2).Where(Alias2.status_active, Alias2.id > 0)) == (
        "SELECT id FROM users AS u2 WHERE status = 'active' AND id > $1",
        [0],
    )
