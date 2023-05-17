import pytest

from pgmini import Array as A, Literal as L, Param as P, Table as T, Tuple, build


t, t2 = T('t'), T('t2')


@pytest.mark.parametrize('value,sql,param', [
    pytest.param([], '()', [], id='empty list'),
    pytest.param([1, 2, 3], '($1, $2, $3)', [1, 2, 3], id='list'),
    pytest.param((), '()', [], id='empty tuple'),
    pytest.param((1, 44), '($1, $2)', [1, 44], id='tuple'),
    pytest.param((1, L(44).Cast('int')), '($1, 44::int)', [1], id='tuple with literal'),
    pytest.param(set(), '()', [], id='empty set'),
    pytest.param({1, 55, 588, 44}, '($1, $2, $3, $4)', list({1, 55, 588, 44}), id='set'),
    pytest.param({}, '()', [], id='empty dict'),
    pytest.param({1: 'a', 56: 'b', 33: 'c'}, '($1, $2, $3)', [1, 56, 33], id='dict'),
    pytest.param(iter([]), '()', [], id='empty generator'),
    pytest.param(iter([1, 6, 3, -1]), '($1, $2, $3, $4)', [1, 6, 3, -1], id='generator'),
])
def test(value, sql: str, param: list):
    assert build(Tuple(value)) == (sql, param)


def test_table_column():
    assert build(Tuple([t.col1, t2.col2.Cast('int'), t.id + t2.id])) == (
        '(t.col1, t2.col2::int, t.id + t2.id)',
        [],
    )


def test_cast_alias():
    assert build(Tuple([P(-1).Cast('smallint'), L(-2)]).Cast('int[]').As('xy')) == (
        '($1::smallint, -2)::int[] AS xy',
        [-1],
    )


def test_operation():
    assert build(t.id.Any(Tuple([t2.id, t2.id2]))) == ('t.id = ANY((t2.id, t2.id2))', [])


def test_array_of_tuple():
    assert build(A([Tuple([t.id, t.id2])])) == ('ARRAY[(t.id, t.id2)]', [])


def test_array_of_tuples():
    assert build(A([Tuple([t.id, t.id2]), Tuple([1, 3])]).Cast('custom_type[]')) == (
        'ARRAY[(t.id, t.id2), ($1, $2)]::custom_type[]',
        [1, 3],
    )
