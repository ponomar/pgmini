import pytest

from pgmini import And, Exists as E, Literal as L, Not, Or, Param as P, Select as S, Table, build

from .utils import compact


t, t2, t3 = Table('t'), Table('t2'), Table('t3')


@pytest.mark.parametrize('cls', [And, Or])
def test_empty(cls):
    assert build(cls()) == (None, [])


@pytest.mark.parametrize('cls', [And, Or])
def test_with_single_element(cls):
    assert build(cls(L(1) == t.column)) == ('1 = t.column', [])


def test_And_with_multiple_elements():
    assert (
        build(And(L(1) == t.column, t.cols == P(25)))
        == ('1 = t.column AND t.cols = $1', [25])
    )


def test_Or_with_multiple_elements():
    assert (
        build(Or(L(1) == t.column, t.cols == P(25)))
        == ('1 = t.column OR t.cols = $1', [25])
    )


@pytest.mark.parametrize('cls', [And, Or])
def test_wrapper_ignored(cls):
    assert build(cls(And(L(1) == 2, L(3) == 4))) == ('1 = $1 AND 3 = $2', [2, 4])
    assert build(cls(Or(L(1) == 2, L(3) == 4))) == ('1 = $1 OR 3 = $2', [2, 4])


def test_And_cast_alias():
    assert build(And(L(1) == 2, L(True) == True).Cast('bool').As('val')) == (  # noqa: E712
        '(1 = $1 AND TRUE IS $2)::bool AS val',
        [2, True],
    )


def test_Or_cast_alias():
    assert build(Or(L(1) == 2, L(None) == P(None)).Cast('bool').As('val')) == (
        '(1 = $1 OR NULL IS $2)::bool AS val',
        [2, None],
    )


def test_Or_without_brackets():
    assert (
        build(Or(L(1) == L(2), L(3) == L(4), L(5) == L(6)))[0]
        == '1 = 2 OR 3 = 4 OR 5 = 6'
    )


def test_Or_with_brackets():
    assert (
        build(And(L(1) == L(2), Or(L(3) == L(4), L(5) == L(6)), L(7) == L(8)))[0]
        == '1 = 2 AND (3 = 4 OR 5 = 6) AND 7 = 8'
    )


def test_And_operationable():
    assert build(And(L(1) == L(2), L(3) == L(4)) == L(5))[0] == '(1 = 2 AND 3 = 4) = 5'


def test_Not():
    assert build(Not(L(1) == 2)) == ('NOT 1 = $1', [2])


def test_Not_cast_alias():
    assert build(Not(L(1) == L(2)).Cast('int').As('X'))[0] == '(NOT 1 = 2)::int AS X'


def test_And_Not():
    assert build(And(Not(L(1) == 0), L(2) == 0))[0] == 'NOT 1 = $1 AND 2 = $2'


def test_Not_And():
    assert build(Not(And(L(1) == 0, L(2) == 0)))[0] == 'NOT (1 = $1 AND 2 = $2)'


def test_Not_Or():
    assert build(Not(Or(L(1) == 0, L(2) == 0)))[0] == 'NOT (1 = $1 OR 2 = $2)'


def test_Not_multiple_operation():
    assert build(Not((L(1) == L(2)) == L(True)))[0] == 'NOT (1 = 2) IS TRUE'


def test_Exists():
    assert build(E(L(1)))[0] == 'EXISTS (1)'


def test_Exists_cast_alias():
    assert build(E(L(True)).Cast('text').As('xyz'))[0] == '(EXISTS (TRUE))::text AS xyz'


def test_Exists_with_multiple_inner_tables():
    q = S(t.id).From(t).Where(E(
        S(t2.id).From(t2)
        .Join(t3, t3.id == t2.id)
        .Where(t2.id == t.id)
    ))
    assert build(q)[0] == compact('''
    SELECT id FROM t
    WHERE EXISTS (
        SELECT t2.id FROM t2
        JOIN t3 ON t3.id = t2.id
        WHERE t2.id = t.id
    )
    ''')
