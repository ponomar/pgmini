import pytest

from pgmini import Array as A, Literal as L, Param as P, Table as T, build


t, t2 = T('t'), T('t2')


@pytest.mark.parametrize('value,sql,param', [
    pytest.param([], 'ARRAY[]', [], id='empty list'),
    pytest.param([1, 2, 3], 'ARRAY[$1, $2, $3]', [1, 2, 3], id='list'),
    pytest.param((), 'ARRAY[]', [], id='empty tuple'),
    pytest.param((1, 44), 'ARRAY[$1, $2]', [1, 44], id='tuple'),
    pytest.param(set(), 'ARRAY[]', [], id='empty set'),
    pytest.param({1, 55, 588, 44}, 'ARRAY[$1, $2, $3, $4]', list({1, 55, 588, 44}), id='set'),
    pytest.param({}, 'ARRAY[]', [], id='empty dict'),
    pytest.param({1: 'a', 56: 'b', 33: 'c'}, 'ARRAY[$1, $2, $3]', [1, 56, 33], id='dict'),
    pytest.param(iter([]), 'ARRAY[]', [], id='empty generator'),
    pytest.param(iter([1, 6, 3, -1]), 'ARRAY[$1, $2, $3, $4]', [1, 6, 3, -1], id='generator'),
])
def test(value, sql: str, param: list):
    assert build(A(value)) == (sql, param)


def test_literal():
    assert build(A([1, L(2).Cast('int'), 3])) == ('ARRAY[$1, 2::int, $2]', [1, 3])


def test_table_column():
    assert build(A([t.col1, t2.col2.Cast('int'), t.id + t2.id])) == (
        'ARRAY[t.col1, t2.col2::int, t.id + t2.id]',
        [],
    )


def test_cast_alias():
    assert build(A([P(-1).Cast('smallint'), L(-2)]).Cast('int[]').As('xy')) == (
        'ARRAY[$1::smallint, -2]::int[] AS xy',
        [-1],
    )


def test_operation():
    assert build(t.id.Any(A([t2.id, t2.id2]))) == ('t.id = ANY(ARRAY[t2.id, t2.id2])', [])
