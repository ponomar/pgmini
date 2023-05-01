from pgmini import Param as P, Select as S, build


def test_asyncpg_dollar_sign():
    assert build(S(1, P('a').Cast('str'))) == ('SELECT $1, $2::str', [1, 'a'])


def test_psycopg2_params():
    sql, params = build(S(1, P('a').Cast('str')), driver='psycopg')
    assert sql == 'SELECT %(p1)s, %(p2)s::str'
    assert params == {'p1': 1, 'p2': 'a'}
