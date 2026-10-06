import os
import time
from typing import Callable
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

USER_AGENT = os.getenv("SCRAPE_USER_AGENT", "scrape-agent/0.1 (learning project)")
MAX_BYTES = 2_000_000

Fetcher = Callable[[str], str]


class HttpFetcher:
    def __init__(self, respect_robots: bool = True, delay: float = 0.0, timeout: float = 15.0):
        self.client = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=timeout, follow_redirects=True)
        self.respect_robots = respect_robots
        self.delay = delay
        self._robots: dict[str, RobotFileParser | None] = {}
        self._last = 0.0

    def allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        p = urlparse(url)
        root = f"{p.scheme}://{p.netloc}"
        if root not in self._robots:
            rp = None
            try:
                r = self.client.get(root + "/robots.txt")
                if r.status_code == 200:
                    rp = RobotFileParser()
                    rp.parse(r.text.splitlines())
            except httpx.HTTPError:
                rp = None
            self._robots[root] = rp
        rp = self._robots[root]
        return rp is None or rp.can_fetch(USER_AGENT, url)

    def __call__(self, url: str) -> str:
        if urlparse(url).scheme not in ("http", "https"):
            raise ValueError(f"only http(s) URLs are supported: {url}")
        if not self.allowed(url):
            raise PermissionError(f"robots.txt disallows {url}")
        wait = self.delay - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        r = self.client.get(url)
        self._last = time.monotonic()
        r.raise_for_status()
        if "html" not in r.headers.get("content-type", "text/html"):
            raise ValueError(f"not an HTML page ({r.headers.get('content-type')})")
        return r.content[:MAX_BYTES].decode(r.encoding or "utf-8", errors="replace")
