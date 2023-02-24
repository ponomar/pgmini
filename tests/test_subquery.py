from pgmini import Select as S, Table as T, build

from .utils import compact


t, t2 = T('t'), T('t2')


def test_separate():
    assert build(S(t.id, t.name).From(t).Where(t.id == 12).Subquery('x')) == (
        '(SELECT id, name FROM t WHERE id = $1) AS x',
        [12],
    )


def test_select():
    sq = (
        S(t.id, t.name).From(t)
        .Where(t.id == 10)
        .OrderBy(t.id.Desc())
        .Limit(1)
        .Subquery('sq')
    )
    sql, params = build(S(sq.id, sq.name.Cast('text').As('name2')).From(sq).Where(sq.id == 100))
    assert sql == compact('''
        SELECT id, name::text AS name2
        FROM (
            SELECT id, name
            FROM t
            WHERE id = $1
            ORDER BY id DESC
            LIMIT $2
        ) AS sq
        WHERE id = $3
    ''')
    assert params == [10, 1, 100]


def test_select_combine_with_usual_table():
    sq = S(t.id, t.name).From(t).Subquery('sq').As('x')
    assert build(S(sq.STAR, t2.name).From(t2, sq).Where(t2.id == sq.id)) == (
        'SELECT x.*, t2.name FROM t2, (SELECT id, name FROM t) AS x WHERE t2.id = x.id',
        [],
    )


def test_join():
    sq = S(t.id).From(t).Subquery('x')
    assert (
        build(S(t2.id, sq.id).From(t2).Join(sq, sq.id == t2.id))[0]
        == 'SELECT t2.id, x.id FROM t2 JOIN (SELECT id FROM t) AS x ON x.id = t2.id'
    )


def test_join_lateral():
    sq = S(t.id).From(t).Where(t.id == t2.id).Subquery('x')
    assert build(S(t2.id, sq.id).From(t2).JoinLateral(sq, True))[0] == compact('''
        SELECT t2.id, x.id
        FROM t2
        JOIN LATERAL (
            SELECT id
            FROM t
            WHERE id = t2.id
        ) AS x ON TRUE
    ''')


def test_left_join_lateral():
    sq = S(t.id).From(t).Where(t.id == t2.id).Subquery('x')
    sql, params = build(S(t2.id, sq.id).From(t2).JoinLateral(sq, sq.id == 11))
    assert sql == compact('''
        SELECT t2.id, x.id
        FROM t2
        JOIN LATERAL (
            SELECT id
            FROM t
            WHERE id = t2.id
        ) AS x ON x.id = $1
    ''')
    assert params == [11]
