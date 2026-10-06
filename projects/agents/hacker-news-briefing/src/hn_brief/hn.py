import html
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urlparse

API = "https://hacker-news.firebaseio.com/v0"
UA = "hn-brief/0.1 (+https://github.com/; personal news scout)"

Getter = Callable[..., object]


@dataclass
class Story:
    id: int
    title: str
    url: str = ""
    score: int = 0
    comments: int = 0
    by: str = ""
    time: int = 0
    text: str = ""
    top_comments: list[str] = field(default_factory=list)
    page_text: str = ""
    kids: list[int] = field(default_factory=list)

    @property
    def domain(self) -> str:
        host = urlparse(self.url).netloc.lower()
        return host[4:] if host.startswith("www.") else host

    @property
    def hn_url(self) -> str:
        return f"https://news.ycombinator.com/item?id={self.id}"

    @classmethod
    def from_item(cls, item: dict) -> "Story":
        return cls(
            id=int(item["id"]),
            title=item.get("title", "").strip(),
            url=item.get("url", "") or "",
            score=int(item.get("score", 0) or 0),
            comments=int(item.get("descendants", 0) or 0),
            by=item.get("by", "") or "",
            time=int(item.get("time", 0) or 0),
            text=html_to_text(item.get("text", "") or ""),
            kids=list(item.get("kids", []) or []),
        )


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        elif tag in ("p", "br", "li", "h1", "h2", "h3", "div"):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(raw: str, limit: int | None = None) -> str:
    if not raw:
        return ""
    p = _TextExtractor()
    try:
        p.feed(raw)
    except Exception:
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()[:limit]
    text = re.sub(r"\s+", " ", "".join(p.parts)).strip()
    return text[:limit] if limit else text


def default_get() -> Getter:
    import requests

    s = requests.Session()
    s.headers["User-Agent"] = UA
    return s.get


class HNClient:
    def __init__(self, get: Getter | None = None, timeout: float = 10.0, workers: int = 8):
        self.get = get or default_get()
        self.timeout = timeout
        self.workers = workers

    def _json(self, path: str):
        r = self.get(f"{API}/{path}", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def top_ids(self, n: int = 60) -> list[int]:
        return list(self._json("topstories.json") or [])[:n]

    def item(self, item_id: int) -> dict | None:
        try:
            return self._json(f"item/{item_id}.json")
        except Exception:
            return None

    def top_stories(self, n: int = 60) -> list[Story]:
        ids = self.top_ids(n)
        with ThreadPoolExecutor(self.workers) as pool:
            items = list(pool.map(self.item, ids))
        return [Story.from_item(i) for i in items
                if i and i.get("type") == "story" and i.get("title") and not i.get("dead") and not i.get("deleted")]

    def top_comments(self, story: Story, k: int = 3) -> list[str]:
        try:
            out = []
            for cid in story.kids[: k * 2]:
                c = self.item(cid)
                if c and not c.get("deleted") and not c.get("dead") and c.get("text"):
                    out.append(html_to_text(c["text"], limit=600))
                if len(out) == k:
                    break
            return out
        except Exception:
            return []

    def page_text(self, url: str, limit: int = 2000, timeout: float = 6.0) -> str:
        if not url.startswith(("http://", "https://")):
            return ""
        try:
            r = self.get(url, timeout=timeout)
            r.raise_for_status()
            ctype = (getattr(r, "headers", {}) or {}).get("Content-Type", "")
            if "html" not in ctype and "text/plain" not in ctype:
                return ""
            return html_to_text(r.text[:400_000], limit=limit)
        except Exception:
            return ""

    def enrich(self, stories: list[Story], comments: bool = True, pages: bool = True) -> None:
        def one(s: Story):
            if comments:
                s.top_comments = self.top_comments(s)
            if pages and s.url:
                s.page_text = self.page_text(s.url)

        with ThreadPoolExecutor(self.workers) as pool:
            list(pool.map(one, stories))
