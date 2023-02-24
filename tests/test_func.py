import pytest

from pgmini import F, Literal as L, Or, Param as P, Select as S, Table, build


t = Table('t')


@pytest.mark.parametrize('func,res,updated', [
    pytest.param(F.count('*'), 'COUNT(*)', [], id='count empty'),
    pytest.param(F.custom_func(), 'CUSTOM_FUNC()', [], id='custom func'),
    pytest.param(F.count('*'), 'COUNT(*)', [], id='count'),
    pytest.param(F.count(L(1)), 'COUNT(1)', [], id='count with literal'),
    pytest.param(F.count(1), 'COUNT($1)', [1], id='count with param'),
    pytest.param(F.count(t.id), 'COUNT(t.id)', [], id='count with column'),
    pytest.param(
        (
            F.count(t.id).Over(partition_by=t.name, order_by=t.age.Desc().NullsLast())
            .Cast('int').As('ololo')
        ),
        '(COUNT(t.id) OVER (PARTITION BY t.name ORDER BY t.age DESC NULLS LAST))::int AS ololo', [],
        id='count with over',
    ),
    pytest.param(
        F.count(55).Over(partition_by=(t.name, L(15), 'xyz', None, True)).As('XY'),
        'COUNT($1) OVER (PARTITION BY t.name, 15, $2, $3, $4) AS XY', [55, 'xyz', None, True],
        id='count with multiple partition by',
    ),
    pytest.param(
        F.count('55').Over(order_by=(t.id, 'xyz')),
        'COUNT($1) OVER (ORDER BY t.id, $2)', ['55', 'xyz'],
        id='count with multiple order by',
    ),
    pytest.param(
        F.date_trunc(L('year'), t.birthday), "DATE_TRUNC('year', t.birthday)", [],
        id='date_trunc with column',
    ),
    pytest.param(
        F.date_trunc(L('day'), '2022-12-11 12:33'), "DATE_TRUNC('day', $1)", ['2022-12-11 12:33'],
        id='date_trunc with param',
    ),
    pytest.param(F.row_number().Over(), 'ROW_NUMBER() OVER ()', [], id='row_number'),
    pytest.param(F.count('*') == 42, 'COUNT(*) = $1', [42], id='count comperable'),
    pytest.param(F.count(t.col.Distinct()), 'COUNT(DISTINCT t.col)', [], id='count distinct'),
    pytest.param(
        F.greatest(t.col, S(t.id).From(t)), 'GREATEST(t.col, (SELECT id FROM t))', [],
        id='select as param',
    ),
    pytest.param(
        F.unnest(P([1, 2]).Cast('int[]'), P(['a', 'b']).Cast('text[]')).As('x(v1, v2)'),
        'UNNEST($1::int[], $2::text[]) AS x(v1, v2)', [[1, 2], ['a', 'b']],
        id='unnest multiple alias',
    ),
    pytest.param(
        F.row_number().Over(partition_by=t.id, order_by=F.date_trunc(L('day'), t.created)),
        "ROW_NUMBER() OVER (PARTITION BY t.id ORDER BY DATE_TRUNC('day', t.created))", [],
        id='func of func',
    ),
    pytest.param(
        F.count('*').Where(t.id == 1, Or(t.name == 'abc', t.pwd == '1234')),
        'COUNT(*) FILTER (WHERE t.id = $1 AND (t.name = $2 OR t.pwd = $3))', [1, 'abc', '1234'],
        id='filter where',
    ),
    pytest.param(
        F.array_agg(t.id + 1).OrderBy(t.id),
        'ARRAY_AGG(t.id + $1 ORDER BY t.id)', [1],
        id='order by',
    ),
    pytest.param(
        F.array_agg(t.id).OrderBy(t.id.Desc().NullsFirst(), t.id2 + 22),
        'ARRAY_AGG(t.id ORDER BY t.id DESC NULLS FIRST, t.id2 + $1)', [22],
        id='order by complex',
    ),
])
def test(func, res: str, updated: list):
    assert build(func) == (res, updated)
