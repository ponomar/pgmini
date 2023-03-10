from pgmini import (
    NULL,
    And,
    Excluded,
    Func as F,
    Insert as Ins,
    Literal as L,
    Or,
    Param as P,
    Select as S,
    Table as T,
    With as W,
    build,
)

from .utils import compact


t, t2 = T('t'), T('t2')


def test():
    assert build(Ins(t, columns=('id', t.name))) == ('INSERT INTO t (id, name)', [])


def test_values():
    q = (
        Ins(t, columns=('c1', 'c2', 'c3', 'c4', 'c5'))
        .Values((1, L(2), 'abc', L('xyz'), P(55).Cast('int')))
    )
    assert build(q) == (
        "INSERT INTO t (c1, c2, c3, c4, c5) VALUES ($1, 2, $2, 'xyz', $3::int)",
        [1, 'abc', 55],
    )


def test_values_multiple():
    q = Ins(t, columns=('c1', 'c2')).Values((1, 2), (3, 4))
    assert build(q) == ('INSERT INTO t (c1, c2) VALUES ($1, $2), ($3, $4)', [1, 2, 3, 4])


def test_returning():
    q = Ins(t, columns=('c1', 'c2')).Returning(t.id1, t.id2)
    assert build(q) == ('INSERT INTO t (c1, c2) RETURNING t.id1, t.id2', [])


def test_returning_star():
    q = Ins(t, columns=('c1', 'c2')).Returning(t.STAR)
    assert build(q) == ('INSERT INTO t (c1, c2) RETURNING t.*', [])


def test_values_full():
    q = Ins(t, columns=('c1', 'c2')).Values((1, 2)).Returning(t.id)
    assert build(q) == ('INSERT INTO t (c1, c2) VALUES ($1, $2) RETURNING t.id', [1, 2])


def test_func_as_value():
    q = Ins(t, columns=('c1', 'c2')).Values((1, F.now())).Returning(t.id)
    assert build(q) == ('INSERT INTO t (c1, c2) VALUES ($1, NOW()) RETURNING t.id', [1])


def test_select():
    q = Ins(t2, columns=('id', 'dt')).Select(
        S(t.id, t.dt)
        .From(t)
        .Where(t.id > 5, t.id < 10)
        .OrderBy(t.id.Desc())
        .Limit(2)
        .Offset(7)
    )
    sql, params = build(q)
    assert sql == compact('''
        INSERT INTO t2 (id, dt)
        SELECT id, dt 
        FROM t 
        WHERE id > $1 AND id < $2
        ORDER BY id DESC 
        LIMIT $3 
        OFFSET $4
    ''')
    assert params == [5, 10, 2, 7]


def test_select_full():
    q = Ins(t2, columns=('id', 'dt')).Select(S(t.id, t.dt).From(t)).Returning(t2.name)
    assert build(q) == ('INSERT INTO t2 (id, dt) SELECT id, dt FROM t RETURNING t2.name', [])


def test_with():
    q1 = S(t.id).From(t).Where(t.id == L(1)).Subquery('s1', materialized=True)
    q2 = S(t2.id).From(t2).Where(t2.id == L(2)).Subquery('s2')

    q = (
        W(q1)
        .Insert(t, columns=('id',))
        .Select(
            S(q1.id.As('id2')).From(q1)
            .Union(S(q2.id).From(q2).Where(q2.id > L(0)))
        )
        .Returning(t.STAR)
    )
    sql, params = build(q)
    assert sql == compact('''
        WITH s1 AS MATERIALIZED (SELECT id FROM t WHERE id = 1)
        INSERT INTO t (id)
        SELECT id AS id2 FROM s1
        UNION SELECT id FROM (SELECT id FROM t2 WHERE id = 2) AS s2 WHERE id > 0
        RETURNING t.*
    ''')
    assert params == []


def test_unnest():
    q = Ins(t, ('id', 'name')).Select(
        S(F.unnest(P([101, 102]).Cast('int[]')), F.unnest(P(['A', 'B']).Cast('text[]')))
    )
    assert build(q) == (
        'INSERT INTO t (id, name) SELECT UNNEST($1::int[]), UNNEST($2::text[])',
        [[101, 102], ['A', 'B']],
    )


def test_from_unnest():
    f = F.unnest(P([101, 102]).Cast('int[]'), P(['A', 'B']).Cast('text[]')).As('x(a, b)')
    q = Ins(t, ('id', 'name')).Select(S(f.a, f.b).From(f))
    assert build(q) == (
        'INSERT INTO t (id, name) SELECT a, b FROM UNNEST($1::int[], $2::text[]) AS x(a, b)',
        [[101, 102], ['A', 'B']],
    )


def test_on_conflict_constraint():
    q = Ins(t, (t.id,)).OnConflict(constraint='cc_uniq', do_nothing=True)
    assert build(q) == ('INSERT INTO t (id) ON CONFLICT ON CONSTRAINT cc_uniq DO NOTHING', [])


def test_on_conflict_index_elements():
    q = Ins(t, (t.id,)).OnConflict(
        index_elements=(
            t.data.Op('->>', 'key1'),
            t.data.Op('->>', 'key2').Cast('int'),
            t.name,
        ),
        do_nothing=True,
    )
    assert build(q) == (
        'INSERT INTO t (id) ON CONFLICT ((data ->> $1), ((data ->> $2)::int), name) DO NOTHING',
        ['key1', 'key2'],
    )


def test_on_conflict_index_where():
    q = Ins(t, (t.id,)).OnConflict(index_elements=(t.id,), index_where=t.id > -5, do_nothing=True)
    assert build(q) == ('INSERT INTO t (id) ON CONFLICT (id) WHERE id > $1 DO NOTHING', [-5])


def test_on_conflict_index_where_multiple():
    q = Ins(t, (t.id,)).OnConflict(
        index_elements=(t.id,),
        index_where=And(
            t.id == NULL,
            Or(t.name.Cast('text') == 'ololo', t.age > P(100).Cast('float')),
        ),
        do_nothing=True,
    )
    sql, params = build(q)
    assert sql == compact('''
        INSERT INTO t (id)
        ON CONFLICT (id)
        WHERE id IS NULL AND (name::text = $1 OR age > $2::float)
        DO NOTHING
    ''')
    assert params == ['ololo', 100]


def test_on_conflict_do_nothing():
    q = Ins(t, (t.id,)).OnConflict(do_nothing=True)
    assert build(q) == ('INSERT INTO t (id) ON CONFLICT DO NOTHING', [])


def test_on_conflict_do_update():
    q = Ins(t, (t.id,)).OnConflict(index_elements=(t.col5,), do_update={t.col1: L(15)})
    assert build(q) == ('INSERT INTO t (id) ON CONFLICT (col5) DO UPDATE SET col1 = 15', [])


def test_on_conflict_do_update_multiple():
    q = Ins(t, (t.id,)).OnConflict(do_update={
        'col1': 12,
        t.col2: t.col2 + 5,
        t.col3: Excluded('col8').Cast('int') * 88,
        t.col4: Excluded(t.col15) * t.col44.Cast('float'),
    })
    sql, params = build(q)
    assert sql == compact('''
        INSERT INTO t (id)
        ON CONFLICT DO UPDATE
        SET col1 = $1,
            col2 = t.col2 + $2,
            col3 = excluded.col8::int * $3,
            col4 = excluded.col15 * t.col44::float
    ''')
    assert params == [12, 5, 88]
