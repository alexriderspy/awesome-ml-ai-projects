import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name


@dataclass
class Dep:
    name: str
    raw: str
    line: int
    specifier: SpecifierSet = field(default_factory=SpecifierSet)
    marker: str = ""
    url: str = ""
    group: str = "main"


@dataclass
class Manifest:
    path: str
    kind: str
    deps: list[Dep]
    requires_python: str = ""
    notes: list[str] = field(default_factory=list)


def _logical_lines(text: str):
    buf, start = "", 0
    for i, line in enumerate(text.splitlines(), 1):
        if not buf:
            start = i
        if line.rstrip().endswith("\\"):
            buf += line.rstrip()[:-1] + " "
            continue
        yield start, buf + line
        buf = ""
    if buf:
        yield start, buf


def _to_dep(req_text: str, line: int, group: str) -> Dep:
    req = Requirement(req_text)
    return Dep(
        name=canonicalize_name(req.name), raw=req_text.strip(), line=line,
        specifier=req.specifier, marker=str(req.marker or ""), url=req.url or "", group=group,
    )


def parse_requirements(text: str, path: str = "requirements.txt") -> Manifest:
    deps, notes = [], []
    for no, line in _logical_lines(text):
        line = re.sub(r"(^|\s)#.*$", "", line).strip()
        if not line:
            continue
        if line.startswith("-"):
            notes.append(f"line {no}: skipped option `{line.split()[0]}`")
            continue
        line = re.sub(r"\s--hash[=\s]\S+", "", line).strip()
        try:
            deps.append(_to_dep(line, no, "main"))
        except InvalidRequirement as e:
            notes.append(f"line {no}: could not parse `{line}` ({e})")
    return Manifest(path, "requirements", deps, notes=notes)


def _find_line(lines: list[str], needle: str, after: int = 0) -> int:
    for i in range(after, len(lines)):
        if needle in lines[i]:
            return i + 1
    return 0


def _poetry_spec(value) -> str:
    if isinstance(value, dict):
        value = value.get("version", "*") if "version" in value else ("@url" if value.keys() & {"git", "url", "path"} else "*")
    value = str(value).strip()
    if value in ("*", ""):
        return ""
    if value == "@url":
        return "@url"
    m = re.fullmatch(r"\^(\d+)(?:\.(\d+))?(?:\.(\d+))?", value)
    if m:
        major, minor, patch = (int(x) if x else 0 for x in m.groups())
        upper = f"{major + 1}.0.0" if major else (f"0.{minor + 1}.0" if minor else f"0.0.{patch + 1}")
        return f">={major}.{minor}.{patch},<{upper}"
    m = re.fullmatch(r"~(\d+)\.(\d+)(?:\.(\d+))?", value)
    if m:
        major, minor = int(m.group(1)), int(m.group(2))
        return f">={major}.{minor}.{m.group(3) or 0},<{major}.{minor + 1}.0"
    if re.fullmatch(r"\d[\w.]*", value):
        return f"=={value}"
    return value


def parse_pyproject(text: str, path: str = "pyproject.toml") -> Manifest:
    data = tomllib.loads(text)
    lines = text.splitlines()
    deps, notes = [], []
    project = data.get("project", {})

    def add(req_text: str, group: str):
        line = _find_line(lines, f'"{req_text}"') or _find_line(lines, req_text)
        try:
            deps.append(_to_dep(req_text, line, group))
        except InvalidRequirement as e:
            notes.append(f"could not parse `{req_text}` ({e})")

    for r in project.get("dependencies", []):
        add(r, "main")
    for extra, reqs in project.get("optional-dependencies", {}).items():
        for r in reqs:
            add(r, f"optional:{extra}")
    for gname, reqs in data.get("dependency-groups", {}).items():
        for r in reqs:
            if isinstance(r, str):
                add(r, f"group:{gname}")

    poetry = data.get("tool", {}).get("poetry", {})
    poetry_tables = [("poetry", poetry.get("dependencies", {}))]
    poetry_tables += [(f"poetry:{g}", t.get("dependencies", {})) for g, t in poetry.get("group", {}).items()]
    for group, table in poetry_tables:
        for name, value in table.items():
            if name.lower() == "python":
                continue
            spec = _poetry_spec(value)
            line = _find_line(lines, f"{name} =") or _find_line(lines, f'"{name}"')
            if spec == "@url":
                deps.append(Dep(canonicalize_name(name), f"{name} (vcs/path)", line, url="vcs", group=group))
                continue
            try:
                deps.append(Dep(canonicalize_name(name), f"{name} {value}", line, SpecifierSet(spec), group=group))
            except Exception as e:
                notes.append(f"could not parse poetry constraint `{name} = {value}` ({e})")

    requires_python = project.get("requires-python", "")
    if not requires_python and isinstance(poetry.get("dependencies", {}).get("python"), str):
        requires_python = _poetry_spec(poetry["dependencies"]["python"])
    return Manifest(path, "pyproject", deps, requires_python=requires_python, notes=notes)


def load(path: str | Path) -> Manifest:
    p = Path(path)
    text = p.read_text()
    if p.suffix == ".toml":
        return parse_pyproject(text, str(p))
    return parse_requirements(text, str(p))
