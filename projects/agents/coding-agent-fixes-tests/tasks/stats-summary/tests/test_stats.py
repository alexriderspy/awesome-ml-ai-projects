import pytest

from mathstats.stats import mean, median


def test_mean():
    assert mean([1, 2]) == 1.5
    assert mean([4, 4, 4]) == 4


def test_median():
    assert median([3, 1, 2]) == 2
    assert median([4, 1, 3, 2]) == 2.5


@pytest.mark.parametrize("fn", [mean, median])
def test_empty(fn):
    with pytest.raises(ValueError):
        fn([])
