from collections import defaultdict
from dataclasses import asdict, dataclass

from packaging.markers import Marker, UndefinedEnvironmentName
from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

from .data import BACKPORTS, LEGACY_COMPAT, STDLIB, STDLIB_FALSE_FRIENDS
from .manifest import Dep, Manifest
from .pypi import PyPIClient

CODES = {
    "DD001": "stdlib module listed as a dependency",
    "DD002": "obsolete backport",
    "DD003": "Python 2 compatibility layer",
    "DD004": "no version constraint",
    "DD005": "lower bound only",
    "DD006": "duplicate entries",
    "DD007": "conflicting constraints",
    "DD008": "pinned to a yanked release",
    "DD009": "pinned version does not exist on PyPI",
}
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


@dataclass
class Finding:
    code: str
    package: str
    line: int
    severity: str
    message: str
    fix: str

    def to_dict(self) -> dict:
        return asdict(self)


def target_python(manifest: Manifest, override: str | None) -> str:
    if override:
        return override
    if manifest.requires_python:
        spec = SpecifierSet(manifest.requires_python)
        for minor in range(0, 20):
            if f"3.{minor}" in spec or f"3.{minor}.0" in spec:
                return f"3.{minor}"
    return "3.11"


def _vt(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def installs_on(dep: Dep, py: str) -> bool:
    if not dep.marker:
        return True
    try:
        return Marker(dep.marker).evaluate({"python_version": py, "python_full_version": f"{py}.0", "extra": ""})
    except UndefinedEnvironmentName:
        return True


def _exact_pin(dep: Dep) -> str | None:
    specs = list(dep.specifier)
    if len(specs) == 1 and specs[0].operator in ("==", "===") and "*" not in specs[0].version:
        return specs[0].version
    return None


def _satisfiable(spec: SpecifierSet) -> bool:
    cands = {"0", "9999"}
    for s in spec:
        v = s.version.replace(".*", "")
        try:
            rel = Version(v).release
        except InvalidVersion:
            return True
        cands.add(v)
        for i in range(len(rel)):
            bumped = list(rel[: i + 1])
            bumped[-1] += 1
            cands.add(".".join(map(str, bumped)))
        cands.add(v + ".1")
    return any(spec.contains(c, prereleases=True) for c in cands)


def check(manifest: Manifest, python: str | None = None, pypi: PyPIClient | None = None) -> list[Finding]:
    py = target_python(manifest, python)
    is_req = manifest.kind == "requirements"
    out: list[Finding] = []
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for dep in manifest.deps:
        counts[(dep.group, dep.name)] += 1

    for dep in manifest.deps:
        name = dep.name
        removable = False
        if name in BACKPORTS:
            since, use = BACKPORTS[name]
            if installs_on(dep, py) and _vt(py) >= _vt(since):
                out.append(Finding("DD002", name, dep.line, "warning",
                                   f"`{name}` backports something the stdlib has had since Python {since}; target is {py}.",
                                   f"Remove it and use `{use}`, or add a marker like `; python_version < \"{since}\"`."))
                removable = True
        elif name in LEGACY_COMPAT:
            out.append(Finding("DD003", name, dep.line, "info",
                               f"`{name}` is a Python 2/3 compatibility layer; on Python {py} it is only needed if a dependency still imports it.",
                               "Drop it once your own code no longer imports it."))
            removable = True
        elif name in STDLIB and name not in STDLIB_FALSE_FRIENDS and installs_on(dep, py):
            out.append(Finding("DD001", name, dep.line, "error",
                               f"`{name}` is a standard-library module; the PyPI package of that name is unrelated or ancient and can break installs.",
                               f"Delete the line; `import {name.replace('-', '_')}` works without it."))
            removable = True
        if removable or dep.url:
            continue

        pin = _exact_pin(dep)
        if not dep.specifier:
            out.append(Finding("DD004", name, dep.line, "warning" if is_req else "info",
                               f"`{name}` has no version constraint, so any future release (including breaking ones) gets installed.",
                               f"Pin it (`{name}==<version>`) in an app, or give it a range (`{name}>=X,<Y`) in a library."))
        elif is_req and counts[(dep.group, name)] == 1 and all(s.operator in (">=", ">") for s in dep.specifier):
            out.append(Finding("DD005", name, dep.line, "info",
                               f"`{name}{dep.specifier}` has no upper bound, so installs are not reproducible.",
                               "Pin an exact version, or use a lock file (pip-tools, uv) to freeze the resolved set."))

        if pin and pypi is not None:
            rel = pypi.release(name, pin)
            if rel and rel.get("missing"):
                out.append(Finding("DD009", name, dep.line, "error",
                                   f"`{name}=={pin}` is not a release on PyPI.", "Check the version number."))
            elif rel and rel.get("yanked"):
                reason = rel.get("yanked_reason") or "no reason given"
                out.append(Finding("DD008", name, dep.line, "error",
                                   f"`{name}=={pin}` was yanked from PyPI ({reason}).",
                                   "Move to the next non-yanked release."))

    by_key: dict[tuple[str, str], list[Dep]] = defaultdict(list)
    for dep in manifest.deps:
        if installs_on(dep, py):
            by_key[(dep.group, dep.name)].append(dep)
    for (group, name), deps in by_key.items():
        if len(deps) < 2:
            continue
        combined = SpecifierSet(",".join(str(d.specifier) for d in deps if d.specifier))
        lines = ", ".join(str(d.line) for d in deps)
        if not _satisfiable(combined):
            out.append(Finding("DD007", name, deps[1].line, "error",
                               f"`{name}` appears {len(deps)} times (lines {lines}) with constraints no version can satisfy: {combined}.",
                               "Keep one entry with the constraint you actually need."))
        else:
            out.append(Finding("DD006", name, deps[1].line, "warning",
                               f"`{name}` appears {len(deps)} times (lines {lines}); the effective constraint is `{combined or 'any'}`.",
                               "Merge them into one line."))

    out.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.line, f.code))
    return out
