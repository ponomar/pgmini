import pytest

from pgmini import Array as A, Literal as L, Param as P, Table as T, build


t, t2 = T('t'), T('t2')


@pytest.mark.parametrize('value', [
    pytest.param([], id='list'),
    pytest.param((), id='tuple'),
    pytest.param(set(), id='set'),
])
def test_empty(value):
    assert build(A(value)) == ('ARRAY[]', [])


def test():
    assert build(A([1, 2, 3])) == ('ARRAY[$1, $2, $3]', [1, 2, 3])


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
