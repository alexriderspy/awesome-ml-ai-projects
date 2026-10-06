import sys

BACKPORTS: dict[str, tuple[str, str]] = {
    "mock": ("3.3", "unittest.mock"),
    "futures": ("3.2", "concurrent.futures"),
    "enum34": ("3.4", "enum"),
    "dataclasses": ("3.7", "dataclasses (stdlib)"),
    "typing": ("3.5", "typing (stdlib)"),
    "pathlib": ("3.4", "pathlib (stdlib)"),
    "pathlib2": ("3.6", "pathlib (stdlib)"),
    "importlib-metadata": ("3.10", "importlib.metadata"),
    "importlib-resources": ("3.11", "importlib.resources"),
    "contextlib2": ("3.7", "contextlib"),
    "functools32": ("3.2", "functools"),
    "subprocess32": ("3.2", "subprocess"),
    "configparser": ("3.2", "configparser (stdlib)"),
    "ipaddress": ("3.3", "ipaddress (stdlib)"),
    "argparse": ("3.2", "argparse (stdlib)"),
    "asyncio": ("3.4", "asyncio (stdlib)"),
    "statistics": ("3.4", "statistics (stdlib)"),
    "singledispatch": ("3.4", "functools.singledispatch"),
    "selectors34": ("3.4", "selectors"),
    "monotonic": ("3.3", "time.monotonic"),
    "scandir": ("3.5", "os.scandir"),
    "backports-zoneinfo": ("3.9", "zoneinfo"),
    "backports-functools-lru-cache": ("3.2", "functools.lru_cache"),
    "backports-ssl-match-hostname": ("3.7", "ssl (stdlib)"),
    "backports-cached-property": ("3.8", "functools.cached_property"),
    "cached-property": ("3.8", "functools.cached_property"),
    "tomli": ("3.11", "tomllib (read-only)"),
    "trollius": ("3.4", "asyncio"),
    "faulthandler": ("3.3", "faulthandler (stdlib)"),
    "unittest2": ("3.2", "unittest"),
    "ordereddict": ("2.7", "collections.OrderedDict"),
}

LEGACY_COMPAT = {"six", "future", "futurize", "python-future", "2to3"}

STDLIB_FALSE_FRIENDS = {"datetime"}

STDLIB = {m.lower().replace("_", "-") for m in sys.stdlib_module_names if not m.startswith("_")}
