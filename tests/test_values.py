import pytest

from pgmini import Literal as L, Select as S, Table as T, Values as V, build


t = T('t')


def test():
    v = V((1, 'a'), (2, 'b')).As('v(id, name)')
    assert build(S(v.id, v.name).From(v)) == (
        'SELECT id, name FROM (VALUES ($1, $2), ($3, $4)) AS v(id, name)',
        [1, 'a', 2, 'b'],
    )


def test_star():
    v = V((1, 'a')).As('v(id, name)')
    assert build(S(v.STAR).From(v)) == ('SELECT * FROM (VALUES ($1, $2)) AS v(id, name)', [1, 'a'])


def test_literal():
    v = V((L(1), L('a'))).As('v(id, name)')
    assert build(S(v.id).From(v)) == ("SELECT id FROM (VALUES (1, 'a')) AS v(id, name)", [])


def test_with_table():
    v = V((1,)).As('v(id)')
    assert build(S(t.id, v.id).From(t, v)) == (
        'SELECT t.id, v.id FROM t, (VALUES ($1)) AS v(id)',
        [1],
    )


def test_join():
    v = V((1,)).As('v(id)')
    assert build(S(t.id).From(t).Join(v, v.id == t.id)) == (
        'SELECT t.id FROM t JOIN (VALUES ($1)) AS v(id) ON v.id = t.id',
        [1],
    )


def test_rows_length_mismatch():
    with pytest.raises(ValueError):
        V((1, 2), (3,))


def test_empty_forbidden():
    with pytest.raises(ValueError):
        V()


def test_alias_required_for_prefix():
    v = V((1,))
    with pytest.raises(ValueError):
        build(S(t.id, v.id).From(t, v))
