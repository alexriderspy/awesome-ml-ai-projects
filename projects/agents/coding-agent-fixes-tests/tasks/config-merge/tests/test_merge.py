from settings.merge import deep_merge

DEFAULTS = {"db": {"host": "localhost", "port": 5432}, "debug": False, "cache": None}


def test_nested_merge():
    out = deep_merge(DEFAULTS, {"db": {"port": 6543}, "debug": True})
    assert out == {"db": {"host": "localhost", "port": 6543}, "debug": True, "cache": None}


def test_inputs_untouched():
    deep_merge(DEFAULTS, {"db": {"host": "prod"}})
    assert DEFAULTS["db"] == {"host": "localhost", "port": 5432}


def test_dict_replaces_scalar():
    out = deep_merge(DEFAULTS, {"cache": {"ttl": 60}})
    assert out["cache"] == {"ttl": 60}
