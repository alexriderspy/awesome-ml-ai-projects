import fnmatch
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROTECTED_NAMES = {"conftest.py", "pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini",
                   "pytest.py", "sitecustomize.py", "usercustomize.py"}
PROTECTED_GLOBS = ("test_*.py", "*_test.py", "*.pth")
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git"}
COPY_IGNORE = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc", "task.json")


def is_protected(rel: str | Path) -> bool:
    parts = Path(rel).parts
    if not parts:
        return False
    if "tests" in parts[:-1] or parts[0] == "tests":
        return True
    name = parts[-1]
    return name in PROTECTED_NAMES or any(fnmatch.fnmatch(name, g) for g in PROTECTED_GLOBS)


def iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for f in sorted(filenames):
            if not f.endswith(".pyc"):
                yield Path(dirpath, f).relative_to(root)


def protected_snapshot(root: Path) -> dict[str, str]:
    snap = {}
    for rel in iter_files(root):
        if is_protected(rel):
            snap[rel.as_posix()] = hashlib.sha256((root / rel).read_bytes()).hexdigest()
    return snap


def tampered_files(original: dict[str, str], current: dict[str, str]) -> list[str]:
    return sorted(p for p in set(original) | set(current) if original.get(p) != current.get(p))


def run_pytest(root: Path, timeout: int = 30, max_chars: int = 3000) -> tuple[bool, str]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    env.pop("PYTHONPATH", None)
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--no-header", "--tb=short"]
    try:
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT: tests did not finish in {timeout}s (infinite loop?)"
    out = (proc.stdout + proc.stderr).strip()
    if len(out) > max_chars:
        out = "...[trimmed]...\n" + out[-max_chars:]
    return proc.returncode == 0, f"exit code {proc.returncode}\n{out}"


class Sandbox:

    def __init__(self, source: str | Path, keep: bool = False):
        self.source = Path(source).resolve()
        self.keep = keep
        self._tmp = tempfile.mkdtemp(prefix="mini_coder_")
        self.root = Path(self._tmp, "repo").resolve()
        shutil.copytree(self.source, self.root, ignore=COPY_IGNORE)
        self.original = protected_snapshot(self.source)

    def resolve(self, rel: str) -> Path:
        if not isinstance(rel, str) or not rel.strip():
            raise PermissionError("empty path")
        if os.path.isabs(rel) or rel.startswith("~"):
            raise PermissionError(f"absolute paths are not allowed: {rel}")
        path = (self.root / rel).resolve()
        if path != self.root and self.root not in path.parents:
            raise PermissionError(f"path escapes the sandbox: {rel}")
        return path

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def tampered(self) -> list[str]:
        return tampered_files(self.original, protected_snapshot(self.root))

    def close(self) -> None:
        if not self.keep:
            shutil.rmtree(self._tmp, ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
