import pytest

from versions.semver import is_newer, parse_version


def test_parse():
    assert parse_version("v1.2.3") == (1, 2, 3)
    assert parse_version("1.10.0") == (1, 10, 0)
    assert parse_version("2.0.13-beta.1") == (2, 0, 13)


def test_compare():
    assert is_newer("1.10.0", "1.9.9")
    assert not is_newer("v0.9.0", "0.10.0")


@pytest.mark.parametrize("bad", ["1a2b3", "1.2", "1.2.3.4", "version 1.2.3", ""])
def test_rejects_junk(bad):
    with pytest.raises(ValueError):
        parse_version(bad)
