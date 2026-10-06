import json
import os
from pathlib import Path

DEFAULT_CACHE = Path(os.getenv("DEP_DOCTOR_CACHE", Path.home() / ".cache" / "dependency-doctor"))


class PyPIClient:
    def __init__(self, cache_dir: str | Path | None = None, offline: bool = False, timeout: float = 10):
        self.cache_dir = Path(cache_dir or DEFAULT_CACHE)
        self.offline = offline
        self.timeout = timeout
        self.fetched = 0

    def _path(self, name: str, version: str) -> Path:
        return self.cache_dir / f"{name}-{version}.json"

    def release(self, name: str, version: str) -> dict | None:
        path = self._path(name, version)
        if path.exists():
            return json.loads(path.read_text())
        if self.offline:
            return None
        import requests

        resp = requests.get(f"https://pypi.org/pypi/{name}/{version}/json", timeout=self.timeout)
        self.fetched += 1
        if resp.status_code == 404:
            info = {"name": name, "version": version, "missing": True, "yanked": False, "yanked_reason": None}
        else:
            resp.raise_for_status()
            d = resp.json()["info"]
            info = {"name": name, "version": version, "missing": False,
                    "yanked": bool(d.get("yanked")), "yanked_reason": d.get("yanked_reason")}
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(info, indent=1))
        return info
