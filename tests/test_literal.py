import pytest

from pgmini import Literal as L, build


@pytest.mark.parametrize('value,res', [
    pytest.param(L('12'), "'12'", id='text'),
    pytest.param(L(15), '15', id='int'),
    pytest.param(L('15').Cast('int'), "'15'::int", id='casted text'),
    pytest.param(L(None), 'NULL', id='None'),
    pytest.param(L(None).Cast('text[]'), 'NULL::text[]', id='casted None'),
    pytest.param(
        L('ololosh').Cast('text').As('other'), "'ololosh'::text AS other",
        id='casted aliased',
    ),
    pytest.param(
        L([101, 102.55, 103, -5, None, '255', True, False, 0, 1]),
        "ARRAY[101, 102.55, 103, -5, NULL, '255', TRUE, FALSE, 0, 1]",
        id='to array',
    ),
])
def test(value: L, res: str):
    assert build(value) == (res, [])  # not modified
