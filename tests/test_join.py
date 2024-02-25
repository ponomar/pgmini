from pgmini import Func as F, Select as S, Table as T, build

from .utils import compact


t, t2, t3 = T('t'), T('t2'), T('t3')


def test_in_ANY():
    q = (
        S(t.id)
        .From(t)
        .Where(t.id.Any(
            S(F.array_agg(t2.col))
            .From(t2)
            .Join(t, t.id == t2.col)
            .Cast('int[]')
        ))
    )
    res = compact('''
        SELECT id FROM t
        WHERE id = ANY(
            ((SELECT ARRAY_AGG(t2.col) FROM t2 JOIN t ON t.id = t2.col)::int[])
        )
    ''')
    assert build(q)[0] == res


def test_in_IN():
    q = (
        S(t.id)
        .From(t)
        .Where(t.id.In(
            S(t2.col)
            .From(t2)
            .Join(t, t.id == t2.col)
        ))
    )
    res = compact('''
        SELECT id FROM t
        WHERE id IN (
            SELECT t2.col FROM t2 JOIN t ON t.id = t2.col
        )
    ''')
    assert build(q)[0] == res
