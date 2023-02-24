from pgmini import NULL, Delete as D, F, Literal as L, Or, Select as S, Table as T, With as W, build

from .utils import compact


t, t2 = T('t'), T('t2')


def test():
    assert build(D(t))[0] == 'DELETE FROM t'


def test_returning():
    q = D(t2).Returning(t2.id, t2.x)
    assert build(q) == ('DELETE FROM t2 RETURNING t2.id, t2.x', [])


def test_returning_star():
    q = D(t2).Returning(t2.STAR)
    assert build(q) == ('DELETE FROM t2 RETURNING t2.*', [])


def test_where():
    q = D(t).Where(t.id > 0, Or(t.name.Cast('text') == 'ololo', t.dt == NULL))
    assert build(q) == (
        'DELETE FROM t WHERE t.id > $1 AND (t.name::text = $2 OR t.dt IS NULL)',
        [0, 'ololo'],
    )


def test_with():
    q1 = S(t.id).From(t).Where(t.id == L(1)).Subquery('s1', materialized=True)
    q2 = S(t2.dt).From(t2).Where(t2.id == L(2))

    q = (
        W(q1)
        .Delete(t)
        .Where(t.id == q1.id, t.dt == q2)
        .Returning(t.STAR)
    )
    sql, params = build(q)
    assert sql == compact('''
        WITH s1 AS MATERIALIZED (SELECT id FROM t WHERE id = 1)
        DELETE FROM t
        WHERE t.id = s1.id AND t.dt = (SELECT dt FROM t2 WHERE id = 2)
        RETURNING t.*
    ''')
    assert params == []


def test_with_nested():
    s = D(t).Where(t.id == 56).Returning(t.name).Subquery('sq')
    q = W(s).Select(S(F.count('*')).From(s).As('cnt'))
    sql, params = build(q)
    assert sql == compact('''
        WITH sq AS (DELETE FROM t WHERE t.id = $1 RETURNING t.name)
        SELECT (SELECT COUNT(*) FROM sq) AS cnt
    ''')
    assert params == [56]
