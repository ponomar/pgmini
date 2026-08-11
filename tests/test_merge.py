import pytest

from pgmini import F, Literal as L, Merge as M, Select as S, Table as T, With as W, build

from .utils import compact


t, t2, src = T('t'), T('t2'), T('src')


def test():
    q = (
        M(t).Using(src, t.id == src.id)
        .WhenMatchedUpdate({t.name: src.name})
        .WhenNotMatchedInsert(('id', 'name'), (src.id, src.name))
    )
    sql, params = build(q)
    assert sql == compact('''
        MERGE INTO t USING src ON t.id = src.id
        WHEN MATCHED THEN UPDATE SET name = src.name
        WHEN NOT MATCHED THEN INSERT (id, name) VALUES (src.id, src.name)
    ''')
    assert params == []


def test_aliased_with_conditions():
    ta, sa = T('target').As('t'), T('source').As('s')
    q = (
        M(ta).Using(sa, ta.id == sa.id)
        .WhenMatchedDelete(condition=sa.deleted == L(True))
        .WhenMatchedUpdate({ta.name: sa.name})
        .WhenNotMatchedInsert((ta.id, ta.name), (sa.id, sa.name), condition=sa.id > 0)
    )
    sql, params = build(q)
    assert sql == compact('''
        MERGE INTO target AS t USING source AS s ON t.id = s.id
        WHEN MATCHED AND s.deleted IS TRUE THEN DELETE
        WHEN MATCHED THEN UPDATE SET name = s.name
        WHEN NOT MATCHED AND s.id > $1 THEN INSERT (id, name) VALUES (s.id, s.name)
    ''')
    assert params == [0]


def test_do_nothing():
    q = (
        M(t).Using(src, t.id == src.id)
        .WhenMatchedDoNothing()
        .WhenNotMatchedDoNothing()
    )
    assert build(q) == (
        'MERGE INTO t USING src ON t.id = src.id '
        'WHEN MATCHED THEN DO NOTHING WHEN NOT MATCHED THEN DO NOTHING',
        [],
    )


def test_values_with_params():
    q = (
        M(t).Using(src, t.id == src.id)
        .WhenNotMatchedInsert(('id', 'status'), (src.id, 'active'))
    )
    assert build(q) == (
        'MERGE INTO t USING src ON t.id = src.id '
        'WHEN NOT MATCHED THEN INSERT (id, status) VALUES (src.id, $1)',
        ['active'],
    )


def test_source_subquery():
    sq = S(t2.id, t2.name).From(t2).Subquery('s')
    q = M(t).Using(sq, t.id == sq.id).WhenMatchedUpdate({t.name: sq.name})
    assert build(q) == (
        'MERGE INTO t USING (SELECT id, name FROM t2) AS s ON t.id = s.id '
        'WHEN MATCHED THEN UPDATE SET name = s.name',
        [],
    )


def test_with_cte_source():
    sq = S(t2.id).From(t2).Subquery('src2')
    q = W(sq).Merge(t).Using(sq, t.id == sq.id).WhenMatchedDelete()
    assert build(q) == (
        'WITH src2 AS (SELECT id FROM t2) '
        'MERGE INTO t USING src2 ON t.id = src2.id WHEN MATCHED THEN DELETE',
        [],
    )


def test_returning():
    q = M(t).Using(src, t.id == src.id).WhenMatchedDelete().Returning(t.id, F.merge_action())
    assert build(q) == (
        'MERGE INTO t USING src ON t.id = src.id WHEN MATCHED THEN DELETE '
        'RETURNING t.id, MERGE_ACTION()',
        [],
    )


def test_using_required():
    with pytest.raises(ValueError):
        build(M(t).WhenMatchedDelete())


def test_when_required():
    with pytest.raises(ValueError):
        build(M(t).Using(src, t.id == src.id))
