import html
import json
import re
from pathlib import Path
from typing import Callable

SearchFn = Callable[[str, int], list[dict]]
FetchFn = Callable[[str], str]


def ddgs_search(query: str, max_results: int = 5) -> list[dict]:
    from ddgs import DDGS

    hits = DDGS().text(query, max_results=max_results) or []
    return [{"title": h.get("title", ""), "url": h.get("href", ""), "snippet": h.get("body", "")} for h in hits if h.get("href")]


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript|svg|header|footer|nav)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()


def httpx_fetch(url: str, max_chars: int = 3000) -> str:
    import httpx

    r = httpx.get(url, timeout=15, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (blog-writer demo)"})
    r.raise_for_status()
    return html_to_text(r.text)[:max_chars]


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2}


class CachedSearch:

    def __init__(self, results: list[dict]):
        self.results = results
        self.returned: set[str] = set()
        self.queries: list[str] = []

    @classmethod
    def from_file(cls, path: str | Path) -> "CachedSearch":
        data = json.loads(Path(path).read_text())
        return cls(data["search_results"] if isinstance(data, dict) else data)

    def __call__(self, query: str, max_results: int = 5) -> list[dict]:
        self.queries.append(query)
        q = _tokens(query)
        scored = [(len(q & _tokens(r["title"] + " " + r["snippet"])), i, r) for i, r in enumerate(self.results)]
        scored.sort(key=lambda t: (-t[0], t[1]))
        hits = [r for s, _, r in scored if s > 0][:max_results]
        self.returned.update(h["url"] for h in hits)
        return hits

    def fetch(self, url: str) -> str:
        for r in self.results:
            if r["url"] == url:
                return r.get("page", r["snippet"])
        raise ValueError(f"not in cache: {url}")
