import re

VERSION_RE = re.compile(r"v?(\d+)\.(\d+)\.(\d+)(?:-[0-9A-Za-z.]+)?$")


def parse_version(text):
    m = VERSION_RE.match(text.strip())
    if not m:
        raise ValueError(f"not a version: {text!r}")
    return tuple(int(g) for g in m.groups())


def is_newer(a, b):
    return parse_version(a) > parse_version(b)
