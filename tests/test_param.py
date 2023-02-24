import pytest

from pgmini import Param, build


@pytest.mark.parametrize('value,res,params', [
    pytest.param(Param(23), '$1', [23], id='int'),
    pytest.param(Param('1.5').Cast('float'), '$1::float', ['1.5'], id='casted'),
    pytest.param(Param(None).Cast('date').As('dt'), '$1::date AS dt', [None],
                 id='None casted aliased'),
])
def test(value: Param, res: str, params: list):
    assert build(value) == (res, params)


def test_index():
    assert build(Param('c')) == ('$1', ['c'])


def test_value_copied():
    raw = [1, 2, 3]
    obj = Param(raw)
    raw.append(4)  # test deepcopy for raw value
    assert build(obj)[1] == [[1, 2, 3]]
