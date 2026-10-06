from cachetools_lite.memo import memoize

calls = []


@memoize
def power(base, exp=2):
    calls.append((base, exp))
    return base ** exp


def test_kwargs_are_part_of_key():
    assert power(2, exp=3) == 8
    assert power(2, exp=5) == 32
    assert power(2) == 4


def test_still_caches():
    calls.clear()
    power(3, exp=4)
    power(3, exp=4)
    assert calls == [(3, 4)]
