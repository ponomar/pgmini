import pytest

from pgmini import (
    And,
    Func as F,
    Literal as L,
    Param as P,
    Select as S,
    Table as T,
    Update as U,
    With as W,
    build,
)

from .utils import compact


t, t2, t3 = T('t'), T('t2'), T('t3')


def test_single_column():
    assert build(S(L(1))) == ('SELECT 1', [])
    assert build(S(L(True))) == ('SELECT TRUE', [])
    assert build(S(L(True).Cast('bool'))) == ('SELECT TRUE::bool', [])

    t = T('tbl')
    assert build(S(t.col5).From(t)) == ('SELECT col5 FROM tbl', [])


def test_few_columns():
    assert build(S(1, 'a', L(False).As('value'), L(True).Cast('bool').As('x'))) == (
        'SELECT $1, $2, FALSE AS value, TRUE::bool AS x',
        [1, 'a'],
    )


def test_from_table():
    assert build(S(t.id, t.name).From(t)) == ('SELECT id, name FROM t', [])


def test_star_from_table():
    assert build(S(t.STAR).From(t)) == ('SELECT * FROM t', [])


def test_from_multiple_tables():
    t1 = T('tbl1')
    t2 = T('user').As('u')
    assert (
        build(S(t1.any, t2.STAR).From(t1, t2))[0]
        == 'SELECT tbl1.any, u.* FROM tbl1, "user" AS u'
    )


def test_join():
    assert (
        build(S(t.id).From(t).Join(t2, t2.name == t.email))[0]
        == 'SELECT t.id FROM t JOIN t2 ON t2.name = t.email'
    )


def test_join_on_true():
    assert (
        build(S(t.id).From(t).Join(t2, True))[0]
        == 'SELECT t.id FROM t JOIN t2 ON TRUE'
    )


def test_join_aliased():
    t2 = T('t2').As('res')
    assert (
        build(S(t.id).From(t).Join(t2, t2.id == t.id))[0]
        == 'SELECT t.id FROM t JOIN t2 AS res ON res.id = t.id'
    )


def test_left_join():
    assert (
        build(S(t.id).From(t).LeftJoin(t2, t2.name == t.email))[0]
        == 'SELECT t.id FROM t LEFT JOIN t2 ON t2.name = t.email'
    )


def test_left_join_on_true():
    assert (
        build(S(t.id).From(t).LeftJoin(t2, True))[0]
        == 'SELECT t.id FROM t LEFT JOIN t2 ON TRUE'
    )


def test_left_join_aliased():
    t2 = T('t2').As('res')
    assert (
        build(S(t.id).From(t).LeftJoin(t2, t2.id == t.id))[0]
        == 'SELECT t.id FROM t LEFT JOIN t2 AS res ON res.id = t.id'
    )


def test_join_multiple():
    t4, t5 = T('t4'), T('t5')
    assert build(
        S(t.id).From(t)
        .Join(t2, t2.id == t.id)
        .LeftJoin(t3, t3.id == t2.id)
        .Join(t4, t4.id == t3.id)
        .LeftJoin(t5, t5.id == t4.id)
    )[0] == compact('''
        SELECT t.id FROM t
        JOIN t2 ON t2.id = t.id
        LEFT JOIN t3 ON t3.id = t2.id
        JOIN t4 ON t4.id = t3.id
        LEFT JOIN t5 ON t5.id = t4.id
    ''')


def test_where():
    assert build(S(t.id).From(t).Where(t.name == 'ololo')) == (
        'SELECT id FROM t WHERE name = $1',
        ['ololo'],
    )


@pytest.mark.parametrize('filters', [
    pytest.param((t.name == 'man', t.age == 25), id='implicit'),
    pytest.param((And(t.name == 'man', t.age == 25),), id='explicit'),
])
def test_where_multiple(filters: tuple):
    assert build(S(t.id).From(t).Where(*filters)) == (
        'SELECT id FROM t WHERE name = $1 AND age = $2',
        ['man', 25],
    )


def test_where_chainable():
    assert (
        build(S(t.id).From(t).Where(t.id == 1).Where(t.age == 0))[0]
        == 'SELECT id FROM t WHERE id = $1 AND age = $2'
    )


def test_add_columns():
    assert build(S(t.id).From(t).AddColumns(t.name, t.age).AddColumns(55)) == (
        'SELECT id, name, age, $1 FROM t',
        [55],
    )


def test_group_by():
    assert build(S(t.id).From(t).GroupBy(t.name))[0] == 'SELECT id FROM t GROUP BY name'


def test_group_by_multiple_tables():
    assert (
        build(S(t.id).From(t, t2).GroupBy(t.name))[0]
        == 'SELECT t.id FROM t, t2 GROUP BY t.name'
    )


def test_group_by_multiple():
    assert build(
        S(t.id, (c2 := F.concat(t.id, t.id2)), (c3 := F.concat(t.id, t.id3).As('x')))
        .From(t)
        .GroupBy(t.id, c2, c3)
    )[0] == compact('''
        SELECT id, CONCAT(id, id2), CONCAT(id, id3) AS x 
        FROM t
        GROUP BY id, CONCAT(id, id2), x
    ''')


def test_group_by_not_chainable():
    q = S(t.id).From(t).GroupBy(t.id)
    with pytest.raises(Exception):
        q.GroupBy(t.name)


def test_having():
    assert build(S(t.id).From(t).Having(t.name == 'x')) == (
        'SELECT id FROM t HAVING name = $1',
        ['x'],
    )


def test_having_multiple():
    assert (
        build(S(t.id).From(t).Having(t.id == L(1), t.name == L('y')))[0]
        == "SELECT id FROM t HAVING id = 1 AND name = 'y'"
    )


def test_having_with_tablename():
    assert (
        build(S(t.id).From(t).Join(t2, t2.id == t.id).Having(t.id == L(1)))[0]
        == "SELECT t.id FROM t JOIN t2 ON t2.id = t.id HAVING t.id = 1"
    )


def test_having_chainable():
    assert (
        build(S(L(1)).From(t).Having(t.id == L(1)).Having(t.age == L(0)))[0]
        == 'SELECT 1 FROM t HAVING id = 1 AND age = 0'
    )


def test_order_by():
    assert build(S(t.id).From(t).OrderBy(t.name))[0] == 'SELECT id FROM t ORDER BY name'


def test_order_by_params():
    assert build(S(t.id).From(t).OrderBy(P(22))) == ('SELECT id FROM t ORDER BY $1', [22])


def test_order_by_multiple():
    assert build(
        S(
            t.id,
            (c2 := F.fn1(t.id2, t.id3).Cast('int')),
            (c3 := F.fn1(t.id4, t.id5).Cast('int').As('xy')),
        )
        .From(t)
        .OrderBy(t.id, c2.Desc(), c3.Desc())
    )[0] == compact('''
        SELECT id, FN1(id2, id3)::int, FN1(id4, id5)::int AS xy
        FROM t
        ORDER BY id, FN1(id2, id3)::int DESC, xy DESC
    ''')


def test_order_by_chainable():
    assert (
        build(S(L(1)).From(t).OrderBy(t.id).OrderBy(t.age))[0]
        == 'SELECT 1 FROM t ORDER BY id, age'
    )


def test_order_by_reset():
    q = S(L(1)).From(t)
    assert build(q.OrderBy(None))[0] == 'SELECT 1 FROM t'
    assert build(q.OrderBy(t.id).OrderBy(None))[0] == 'SELECT 1 FROM t'
    assert (
        build(q.OrderBy(t.id).OrderBy(None).OrderBy(t.name))[0]
        == 'SELECT 1 FROM t ORDER BY name'
    )


def test_order_by_None_forbidden():
    q = S(L(1)).From(t)
    with pytest.raises(Exception):
        q.OrderBy(t.id, None)


def test_order_by_desc():
    assert build(S(L(1)).From(t).OrderBy(t.id.Desc()))[0] == 'SELECT 1 FROM t ORDER BY id DESC'


def test_order_by_nulls_last():
    assert (
        build(S(L(1)).From(t).OrderBy(t.id.NullsLast()))[0]
        == 'SELECT 1 FROM t ORDER BY id NULLS LAST'
    )


def test_order_by_nulls_first():
    assert (
        build(S(L(1)).From(t).OrderBy(t.id.NullsFirst()))[0]
        == 'SELECT 1 FROM t ORDER BY id NULLS FIRST'
    )


def test_order_by_desc_nulls_first():
    assert (
        build(S(L(1)).From(t).OrderBy(t.id.Desc().NullsFirst()))[0]
        == 'SELECT 1 FROM t ORDER BY id DESC NULLS FIRST'
    )


def test_order_by_nulls_rewrite():
    assert (
        build(S(L(1)).From(t).OrderBy(t.id.NullsFirst().NullsLast()))[0]
        == 'SELECT 1 FROM t ORDER BY id NULLS LAST'
    )


def test_limit():
    assert build(S(L(1)).Limit(3)) == ('SELECT 1 LIMIT $1', [3])


def test_limit_literal():
    assert build(S(L('x')).Limit(L(5))) == ("SELECT 'x' LIMIT 5", [])


def test_limit_reset():
    q = S(L(1)).Limit(L(5))
    assert build(q)[0] == 'SELECT 1 LIMIT 5'
    assert build(q.Limit(None))[0] == 'SELECT 1'


def test_offset():
    assert build(S(L(1)).Offset(3)) == ('SELECT 1 OFFSET $1', [3])


def test_offset_literal():
    assert build(S(L('x')).Offset(L(5))) == ("SELECT 'x' OFFSET 5", [])


def test_offset_reset():
    q = S(L(1)).Offset(L(5))
    assert build(q)[0] == 'SELECT 1 OFFSET 5'
    assert build(q.Offset(None))[0] == 'SELECT 1'


def test_limit_offset():
    assert (
        build(S(L(1)).From(t).Limit(L(10)).Offset(L(1)))[0]
        == 'SELECT 1 FROM t LIMIT 10 OFFSET 1'
    )


def test_select_alias():
    assert (
        build(S(L(1), S(t2.id).From(t2).Where(t2.id == t.id).As('count')).From(t))[0]
        == 'SELECT 1, (SELECT id FROM t2 WHERE id = t.id) AS count FROM t'
    )


def test_select_cast_alias():
    assert build(
        S(
            1,
            S(t2.id).From(t2).Where(t2.id == t.id, t2.age == 10).Cast('int').As('count'),
        )
        .From(t)
    ) == (
        'SELECT $1, ((SELECT id FROM t2 WHERE id = t.id AND age = $2)::int) AS count FROM t',
        [1, 10],
    )


def test_union():
    q = S(L(1)).From(t).Where(t.id == 3)
    assert (
        build(q.Union(S(L(5))))
        == ('SELECT 1 FROM t WHERE id = $1 UNION SELECT 5', [3])
    )
    assert build(q)[0] == 'SELECT 1 FROM t WHERE id = $1'  # immutable


def test_union_all():
    q = S(L(1)).From(t).Where(t.id == 3)
    assert (
        build(q.UnionAll(S(L(5))))
        == ('SELECT 1 FROM t WHERE id = $1 UNION ALL SELECT 5', [3])
    )
    assert build(q)[0] == 'SELECT 1 FROM t WHERE id = $1'  # immutable


def test_union_order_by():
    # It is incorrect SQL, but we do not want to complicate codebase to guess what developer means.
    # If you need to ORDER BY with UNIONs, just wrap UNIONated query into subquery
    # and apply ORDER BY on it.
    # It will be more understandable in compiled sql as well.
    q1 = S(t.id).From(t).Where(t.id == L(0))
    q2 = S(t2.id).From(t2).Where(t2.id == L(-1))
    assert (
        build(q1.OrderBy(t.id.Desc()).Union(q2.OrderBy(t2.id.Desc())))[0]
        == compact('''
            SELECT id FROM t
            WHERE id = 0
            ORDER BY id DESC
            UNION
            SELECT id FROM t2
            WHERE id = -1
            ORDER BY id DESC
        ''')
    )

    # Correct way
    sq = q1.Union(q2).Subquery('x')
    assert (
        build(S(sq.id).From(sq).OrderBy(sq.id.Desc()).Limit(L(2)).Offset(L(10)))[0]
        == compact('''
            SELECT id FROM
            (
                SELECT id FROM t WHERE id = 0
                UNION
                SELECT id FROM t2 WHERE id = -1
            ) AS x
            ORDER BY id DESC
            LIMIT 2
            OFFSET 10
        ''')
    )


def test_union_multiple():
    assert build(
        S(L('x'))
        .Union(S(L('a')))
        .UnionAll(S(L('b')))
        .Union(S(L('c')))
        .UnionAll(S(L('d')))
    )[0] == compact('''
        SELECT 'x'
        UNION SELECT 'a'
        UNION ALL SELECT 'b'
        UNION SELECT 'c'
        UNION ALL SELECT 'd'
    ''')


def test_union_order_by_and_limit_offset():
    q = S(L(1)).From(t).Where(t.id == L(4)).Limit(L(7)).Offset(L(15))
    assert (
        build(q.Union(S(L(5)).Limit(L(6)).Offset(L(16))))[0]
        == 'SELECT 1 FROM t WHERE id = 4 LIMIT 7 OFFSET 15 UNION SELECT 5 LIMIT 6 OFFSET 16'
    )


def test_with():
    sq = S(t.id, t.name).From(t).Where(t.name == 'xyz').Limit(5).Subquery('sq')
    sql, params = build(W(sq).Select(sq.id, sq.name).From(sq).Where(sq.id == 16))
    assert sql == compact('''
        WITH sq AS (
            SELECT id, name
            FROM t
            WHERE name = $1
            LIMIT $2
        )
        SELECT id, name
        FROM sq
        WHERE id = $3
    ''')
    assert params == ['xyz', 5, 16]


def test_with_multiple():
    x1 = S(t.id).From(t).Subquery('x1', materialized=True)
    x2 = S(t2.id).From(t2).Subquery('x2')
    assert (
        build(W(x1, x2).Select(x1.id, x2.id.As('id2')).From(x1, x2).Where(x1.id == x2.id))[0]
        == compact('''
            WITH x1 AS MATERIALIZED (SELECT id FROM t),
            x2 AS (SELECT id FROM t2)
            SELECT x1.id, x2.id AS id2
            FROM x1, x2
            WHERE x1.id = x2.id
        ''')
    )


def test_with_join():
    x1 = S(t.id).From(t).Subquery('x1')
    x2 = S(t2.id).From(t2).Subquery('x2')
    assert (
        build(W(x1, x2).Select(x1.id).From(x1).Join(x2, x2.id == x1.id))[0]
        == compact('''
            WITH x1 AS (SELECT id FROM t),
            x2 AS (SELECT id FROM t2)
            SELECT x1.id
            FROM x1
            JOIN x2 ON x2.id = x1.id
        ''')
    )


def test_with_join_mixed():
    x1 = S(t.id).From(t).Subquery('x1')
    x2 = S(t2.id).From(t2).Subquery('x2')
    x3 = S(t3.id).From(t3).Subquery('x3')
    assert build(
        W(x1, x2)
        .Select(x1.id)
        .From(x1)
        .Join(x2, x2.id == x1.id)
        .Join(x3, x3.id == x2.id)
    )[0] == compact('''
        WITH x1 AS (SELECT id FROM t),
        x2 AS (SELECT id FROM t2)
        SELECT x1.id
        FROM x1
        JOIN x2 ON x2.id = x1.id
        JOIN (SELECT id FROM t3) AS x3 ON x3.id = x2.id
    ''')


def test_get_columns():
    s = S(
        L('a'),
        L(None).As('fst'),
        P(135),
        P(999).As('two'),
        t.id,
        t.id.As('id2'),
        t.id == 55,
        (t.id == 55).As('op'),
    )
    assert s.GetColumns() == (None, 'fst', None, 'two', 'id', 'id2', None, 'op')


def test_select_of_select_in_brackets():
    s = S(L('abc'), S(L('xyz')).From(t))
    assert build(s)[0] == "SELECT 'abc', (SELECT 'xyz' FROM t)"


def test_select_from_function():
    f = F.unnest(P([1]).Cast('int[]'), P(['a']).Cast('text[]')).As('w(a, b)')
    assert build(S(f.a, f.b).From(f)) == (
        'SELECT a, b FROM UNNEST($1::int[], $2::text[]) AS w(a, b)',
        [[1], ['a']],
    )


def test_select_star_from_function():
    f = F.unnest(P([1]).Cast('int[]'))
    assert build(S(f.STAR).From(f)) == ('SELECT * FROM UNNEST($1::int[])', [[1]])


def test_select_star_from_aliased_function():
    f = F.unnest(P([1]).Cast('int[]')).As('w(a)')
    assert build(S(f.STAR).From(f)) == ('SELECT * FROM UNNEST($1::int[]) AS w(a)', [[1]])


def test_distinct_on():
    assert build(S(t.id, t.name).From(t).DistinctOn(t.position)) == (
        'SELECT DISTINCT ON (position) id, name FROM t',
        [],
    )


def test_distinct_on_multiple_with_params():
    assert build(S(t.id, t.name).From(t).DistinctOn(t.id, F.concat(t.name, 'suffix'))) == (
        'SELECT DISTINCT ON (id, CONCAT(name, $1)) id, name FROM t',
        ['suffix'],
    )


def test_nested_select_in_with_stmt():
    s = S(t.id).From(t).Subquery('sq')
    res, args = build(W(s).Select(S(s.id).From(s).As('res')))
    assert res == 'WITH sq AS (SELECT id FROM t) SELECT (SELECT id FROM sq) AS res'
    assert args == []


def test_nested_select_upd_in_with_stmt():
    sq = U(t).Set({t.id: t.id2}).Returning(t.id).Subquery('sq')
    res, args = build(W(sq).Select(S(sq.id).From(sq).As('res')))
    assert (
        res
        == 'WITH sq AS (UPDATE t SET id = t.id2 RETURNING t.id) SELECT (SELECT id FROM sq) AS res'
    )
    assert args == []
