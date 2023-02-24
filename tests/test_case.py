from pgmini import Case as C, Literal as L, Select as S, Table as T, build

from .utils import compact


t, t2 = T('t'), T('t2')


def test():
    assert build(C((L(1) == 2, L(True)))) == ('CASE WHEN 1 = $1 THEN TRUE END', [2])


def test_multiple():
    assert build(C((L(1) == 1, 1), (L(2) == 2, 2))) == (
        'CASE WHEN 1 = $1 THEN $2 WHEN 2 = $3 THEN $4 END',
        [1, 1, 2, 2],
    )


def test_else():
    assert build(C((L(1) == L(1), L(1)), Else=True)) == (
        'CASE WHEN 1 = 1 THEN 1 ELSE $1 END',
        [True],
    )


def test_else_literal_none():
    assert (
        build(C((L(1) == L(1), L(1)), Else=L(None)))[0]
        == 'CASE WHEN 1 = 1 THEN 1 ELSE NULL END'
    )


def test_cast_alias():
    assert (
        build(C((L(1) == L(1), L(1))).Cast('int').As('res'))[0]
        == '(CASE WHEN 1 = 1 THEN 1 END)::int AS res'
    )


def test_immutable():
    c1 = C((L(1) == 1, 1))
    c2 = c1.Cast('int')
    c3 = c2.As('x')
    assert c1 is not c2
    assert c2 is not c3


def test_columns():
    assert (
        build(C((t.id == t2.id, t.id), Else=t2.name))[0]
        == 'CASE WHEN t.id = t2.id THEN t.id ELSE t2.name END'
    )


def test_in_select():
    sql, params = build(
        S(C((L(2) == 2, False), Else=True).Distinct().As('x2'))
        .From(t)
        .Where(t.id == C((L(5) == 5, 1), (L(6) == 6, 2), Else=3).Cast('int'))
        .OrderBy(C((L(7) == 7, 0), Else=1).Desc().NullsLast())
        .Limit(C((L(8) == 8, 29), Else=30))
        .Offset(C((L(9) == 9, 31), Else=32))
    )
    assert sql == compact('''
        SELECT DISTINCT CASE WHEN 2 = $1 THEN $2 ELSE $3 END AS x2
        FROM t
        WHERE id = (CASE WHEN 5 = $4 THEN $5 WHEN 6 = $6 THEN $7 ELSE $8 END)::int
        ORDER BY CASE WHEN 7 = $9 THEN $10 ELSE $11 END DESC NULLS LAST
        LIMIT CASE WHEN 8 = $12 THEN $13 ELSE $14 END
        OFFSET CASE WHEN 9 = $15 THEN $16 ELSE $17 END
    ''')
    assert params == [2, False, True, 5, 1, 6, 2, 3, 7, 0, 1, 8, 29, 30, 9, 31, 32]
