from datetime import date

import pytest

from pgmini import F, Literal as L, Param as P, Select as S, Table, build


t, t2 = Table('t'), Table('t2')


@pytest.mark.parametrize('left,right,res,updated', [
    pytest.param(t.col, 'Kyiv', 't.col = $1', ['Kyiv'], id='column to text'),
    pytest.param(t.col, None, 't.col IS $1', [None], id='column to None'),
    pytest.param(t.col, True, 't.col IS $1', [True], id='column to True'),
    pytest.param(t.col, False, 't.col IS $1', [False], id='column to False'),
    pytest.param(t.col, 0, 't.col = $1', [0], id='column to 0'),
    pytest.param(t.col, 1, 't.col = $1', [1], id='column to 1'),
    pytest.param(t.col.Cast('int'), 1, 't.col::int = $1', [1], id='casted column to 1'),
    pytest.param(t.col, L(None), 't.col IS NULL', [], id='column to literal None'),
    pytest.param(t.col, L(True), 't.col IS TRUE', [], id='column to literal True'),
    pytest.param(t.col, L(False), 't.col IS FALSE', [], id='column to literal False'),
    pytest.param(t.col, L(1), 't.col = 1', [], id='column to literal 1'),
    pytest.param(t.col, L(1).Cast('float'), 't.col = 1::float', [], id='column to casted literal'),
    pytest.param(t.col, P(None), 't.col IS $1', [None], id='column to param None'),
    pytest.param(t.col, P(True), 't.col IS $1', [True], id='column to param True'),
    pytest.param(t.col, P(False), 't.col IS $1', [False], id='column to param False'),
    pytest.param(t.col, P(0), 't.col = $1', [0], id='column to param 0'),
    pytest.param(t.col, P(1), 't.col = $1', [1], id='column to param 1'),
    pytest.param(t.col, P('str'), 't.col = $1', ['str'], id='column to param text'),
    pytest.param(
        t.col, P('str2').Cast('text'), 't.col = $1::text', ['str2'],
        id='column to casted param',
    ),
    pytest.param(L(12), L(15), '12 = 15', [], id='literal int to literal int'),
    pytest.param(
        P('some text'), L(15), '$1 = 15', ['some text'],
        id='param text to literal int',
    ),
    pytest.param(
        P('str').Cast('text'), P(True), '$1::text IS $2', ['str', True],
        id='casted param text to param True',
    ),
    pytest.param(
        P('ololo').Cast('int'), t.col2.Cast('numeric'),
        '$1::int = t.col2::numeric', ['ololo'],
        id='casted param text to casted column',
    ),
    pytest.param(
        P('one') == P('two'), P('three'),
        '($1 = $2) = $3', ['one', 'two', 'three'],
        id='(param compared to param) compared to param',
    ),
    pytest.param(
        L('one') == P('two'), P('three') == t.cols.Cast('int'),
        "('one' = $1) = ($2 = t.cols::int)", ['two', 'three'],
        id='(literal compared to param) compared to (param compared to casted column)',
    ),
])
def test_equal(left, right, res: str, updated: list):
    assert build(left == right) == (res, updated)


def test_multiple():
    assert build((L(1) == L(2)) == L(True))[0] == '(1 = 2) IS TRUE'


@pytest.mark.parametrize('operation,res,updated', [
    pytest.param(L('one') != P('two'), "'one' != $1", ['two'], id='literal not equal to param'),
    pytest.param(L('one') != t.col, "'one' != t.col", [], id='literal not equal to column'),
    pytest.param(L(18) != P(None), '18 IS NOT $1', [None], id='literal is not param'),
    pytest.param(L(18) > L(15), '18 > 15', [], id='literal > literal'),
    pytest.param(L(18) >= L(18), '18 >= 18', [], id='literal >= literal'),
    pytest.param(L(33) < L(45), '33 < 45', [], id='literal < literal'),
    pytest.param(L(34) <= L(34), '34 <= 34', [], id='literal <= literal'),
    pytest.param(L(22) + L(33), '22 + 33', [], id='literal + literal'),
    pytest.param(L(10) - L(1), '10 - 1', [], id='literal - literal'),
    pytest.param(L(12) * L(15), '12 * 15', [], id='literal * literal'),
    pytest.param(L(12) / L(4), '12 / 4', [], id='literal / literal'),
    pytest.param(L(12) / L(4).Cast('float'), '12 / 4::float', [], id='literal / casted literal'),
    pytest.param(L(18).Is(L(19)), '18 IS 19', [], id='literal is literal'),
    pytest.param(L(15).IsNot(L(True)), '15 IS NOT TRUE', [], id='literal is not literal'),
    pytest.param(
        P('abc').In([
            L(True), L(None), L(False), P(None), P(True), P(False), t.col.Cast('text'),
            L(88), P(44),
        ]),
        '$1 IN (TRUE, NULL, FALSE, $2, $3, $4, t.col::text, 88, $5)',
        ['abc', None, True, False, 44], id='IN',
    ),
    pytest.param(
        t.col.In(S(t2.col).From(t2).Where(t2.id == 1).Limit(2)),
        't.col IN (SELECT col FROM t2 WHERE id = $1 LIMIT $2)', [1, 2],
        id='IN query',
    ),
    pytest.param(
        t.col2.NotIn([t.col1, t.col3, 47, L(51)]).Distinct().Cast('bool').As('xyz'),
        'DISTINCT (t.col2 NOT IN (t.col1, t.col3, $1, 51))::bool AS xyz', [47], id='NOT IN',
    ),
    pytest.param(
        t.col.NotIn(S(t2.col).From(t2)), 't.col NOT IN (SELECT col FROM t2)', [],
        id='NOT IN query',
    ),
    pytest.param(
        t.col2.Any(obj1 := [22, 23, 24, 25]).Distinct().Cast('float').As('cba'),
        'DISTINCT (t.col2 = ANY($1))::float AS cba', [obj1], id='ANY raw',
    ),
    pytest.param(t.col.Any(obj2 := (22, 23, 24)), 't.col = ANY($1)', [obj2], id='ANY as tuple'),
    pytest.param(t.col.Any(obj3 := {1, 3, 5}), 't.col = ANY($1)', [obj3], id='ANY as set'),
    pytest.param(t.col.Any(obj4 := {1: 'a', 33: 'b'}), 't.col = ANY($1)', [obj4], id='ANY as dict'),
    pytest.param(
        t.col2.Any(P([1, 2]).Cast('int[]')), 't.col2 = ANY($1::int[])',
        [[1, 2]], id='ANY param',
    ),
    pytest.param(t.col.Op('->', L('path')), "t.col -> 'path'", [], id='custom'),
    pytest.param(
        t.col.Op('#>', L(['l1', 'l2'])), "t.col #> ARRAY['l1', 'l2']", [],
        id='custom literal',
    ),
    pytest.param(
        t.col.Op('#>', P(['l1', 'l2'])).Cast('int').As('sq'),
        '(t.col #> $1)::int AS sq', [['l1', 'l2']], id='custom param',
    ),
    pytest.param(
        t.col.Op('#>', ['l1', 'l2']),
        't.col #> $1', [['l1', 'l2']], id='custom raw param',
    ),
    pytest.param(t.col.Between(L(1), L(2)), 't.col BETWEEN 1 AND 2', [], id='between'),
    pytest.param(
        t.col.Between(P(1).Cast('int'), 25), 't.col BETWEEN $1::int AND $2', [1, 25],
        id='between with params',
    ),
    pytest.param(
        t.col.Between(t.col2, t2.x), 't.col BETWEEN t.col2 AND t2.x', [],
        id='between with columns',
    ),
    pytest.param(
        (
            t.col.Between(L(date(2022, 11, 5)).Cast('date'), L(date(2022, 11, 6)))
            .Cast('bool').As('fld')
        ),
        "(t.col BETWEEN '2022-11-05'::date AND '2022-11-06')::bool AS fld", [],
        id='between cast and alias',
    ),
    pytest.param(t.col.Like(L('%xxx%')), "t.col LIKE '%xxx%'", [], id='like'),
    pytest.param(t.col.Like('%xxx%'), 't.col LIKE $1', ['%xxx%'], id='like with params'),
    pytest.param(
        t.col.Like(t.col2.Cast('text')).Cast('int').As('f1'),
        '(t.col LIKE t.col2::text)::int AS f1', [],
        id='like cast alias',
    ),
    pytest.param(t.col.Ilike(L('%abc')), "t.col ILIKE '%abc'", [], id='ilike'),
    pytest.param(t.col.Ilike('xyz'), 't.col ILIKE $1', ['xyz'], id='ilike with params'),
    pytest.param(
        t.col.Ilike(t.col2.Cast('text')).Cast('int').As('f1'),
        '(t.col ILIKE t.col2::text)::int AS f1', [],
        id='ilike cast alias',
    ),
    pytest.param(
        t.col.Op('at time zone', L('UTC')), "t.col at time zone 'UTC'", [],
        id='at time zone',
    ),
    pytest.param(
        t.col.Op('at time zone', 'UTC').Op('at time zone', 'Europe/Kyiv').Cast('int').As('az'),
        "((t.col at time zone $1) at time zone $2)::int AS az", ['UTC', 'Europe/Kyiv'],
        id='at time zone twice',
    ),
    pytest.param(
        t.col[2].Cast('text').As('xx'),
        "(t.col[$1])::text AS xx", [2],
        id='slice by index',
    ),
    pytest.param(
        t.col1[t.col2],
        "t.col1[t.col2]", [],
        id='slice by dynamic index',
    ),
    pytest.param(
        t.col[3:F.array_length(t.col, 1)],
        "t.col[$1:ARRAY_LENGTH(t.col, $2)]", [3, 1],
        id='slice by range',
    ),
    pytest.param(
        t.col[:5],
        "t.col[:$1]", [5],
        id='slice till index',
    ),
    pytest.param(
        t.col[4:],
        "t.col[$1:]", [4],
        id='slice from index',
    ),
    pytest.param(
        t.col.Cast('int[]')[1],
        "(t.col::int[])[$1]", [1],
        id='slice with brackets',
    ),
])
def test_other(operation, res: str, updated: list):
    assert build(operation) == (res, updated)
