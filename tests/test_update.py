from pgmini import (
    NULL,
    Func as F,
    Literal as L,
    Or,
    Param as P,
    Select as S,
    Table as T,
    Update as U,
    With as W,
    build,
)

from .utils import compact


t, t2 = T('t'), T('t2')


def test():
    assert build(U(t).Set({'a': NULL})) == ('UPDATE t SET a = NULL', [])


def test_multiple():
    q = U(t).Set({t.col1: 1, t.col2: P(2).Cast('float'), t.col3: t.col4 + F.greatest(t.col5, 55)})
    assert build(q) == (
        'UPDATE t SET col1 = $1, col2 = $2::float, col3 = t.col4 + GREATEST(t.col5, $3)',
        [1, 2, 55],
    )


def test_returning():
    q = U(t).Set({'a': L(1)}).Returning(t.id1, t.id2)
    assert build(q) == ('UPDATE t SET a = 1 RETURNING t.id1, t.id2', [])


def test_returning_star():
    q = U(t).Set({'a': NULL}).Returning(t.STAR)
    assert build(q) == ('UPDATE t SET a = NULL RETURNING t.*', [])


def test_where():
    q = U(t2).Set({'a': NULL}).Where(t2.id == 44, Or(t2.name == 'txt', t2.age.Cast('int') < 100))
    sql, params = build(q)
    assert sql == compact('''
        UPDATE t2 SET a = NULL
        WHERE t2.id = $1 AND (t2.name = $2 OR t2.age::int < $3)
    ''')
    assert params == [44, 'txt', 100]


def test_from():
    q = U(t).Set({'a': L(0)}).From(t2)
    assert build(q) == ('UPDATE t SET a = 0 FROM t2', [])


def test_from_where():
    q = U(t).Set({'a': L(0)}).From(t2).Where(t2.id == t.id)
    assert build(q) == ('UPDATE t SET a = 0 FROM t2 WHERE t2.id = t.id', [])


def test_with():
    q1 = S(t.id).From(t).Where(t.id == L(1)).Subquery('s1', materialized=True)
    q2 = S(t2.id).From(t2).Where(t2.id == L(2)).Subquery('s2')

    q = (
        W(q1)
        .Update(t)
        .Set({t.id: q1.id, t.name: q2.name})
        .From(q1, q2)
        .Where(q1.id == t.id - 3, q2.name == q1.name)
        .Returning(t.STAR)
    )
    sql, params = build(q)
    assert sql == compact('''
        WITH s1 AS MATERIALIZED (SELECT id FROM t WHERE id = 1)
        UPDATE t SET id = s1.id, name = s2.name
        FROM s1, (
            SELECT id
            FROM t2
            WHERE id = 2
        ) AS s2
        WHERE s1.id = (t.id - $1) AND s2.name = s1.name
        RETURNING t.*
    ''')
    assert params == [3]
