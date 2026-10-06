import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urldefrag

DROP_TAGS = {"script", "style", "noscript", "svg", "iframe", "template", "form", "button", "select", "nav", "footer"}
VOID_TAGS = {"br", "img", "hr", "input", "meta", "link", "source", "wbr", "area", "col", "base", "embed"}
BLOCK_TAGS = {"p", "div", "section", "article", "main", "aside", "header", "ul", "ol", "dl", "blockquote",
              "figure", "figcaption", "address", "pre", "table", "tr", "li", "dt", "dd",
              "h1", "h2", "h3", "h4", "h5", "h6"}
JUNK_ATTR = re.compile(r"cookie|consent|advert|\bads?\b|ad-slot|newsletter|popup|modal|share", re.I)
PAGER_ATTR = re.compile(r"pag(e|ination|er)", re.I)
RATING_ATTR = re.compile(r"rating", re.I)
NEXT_TEXT = re.compile(r"\bnext\b|\bolder\b|\bmore\b|›|»|→", re.I)


@dataclass
class Page:
    url: str
    title: str
    markdown: str
    links: list[dict] = field(default_factory=list)

    def next_candidates(self) -> list[dict]:
        out = []
        for ln in self.links:
            short = len(ln["text"].split()) <= 4
            if "next" in ln["rel"] or (short and NEXT_TEXT.search(ln["text"])):
                out.append(ln)
        return out


def _should_drop(tag: str, attrs: dict) -> bool:
    marker = " ".join(str(attrs.get(k) or "") for k in ("class", "id", "role", "aria-label"))
    if tag == "nav" and PAGER_ATTR.search(marker):
        return False
    if tag in DROP_TAGS:
        return True
    if "hidden" in attrs or attrs.get("aria-hidden") == "true":
        return True
    if re.search(r"display\s*:\s*none", attrs.get("style") or "", re.I):
        return True
    return bool(JUNK_ATTR.search(marker))


class _Cleaner(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base = base_url
        self.title = ""
        self.links: list[dict] = []
        self.bufs: list[list[str]] = [[]]
        self.skip: tuple[str, int] | None = None
        self.in_title = False
        self.anchors: list[dict] = []
        self.tables: list[list[list[str]]] = []
        self.list_depth = 0

    def _emit(self, s: str) -> None:
        self.bufs[-1].append(s)

    def _newline(self) -> None:
        self._emit("\n")

    def handle_starttag(self, tag, attrs_list):
        attrs = dict(attrs_list)
        if self.skip:
            if tag == self.skip[0] and tag not in VOID_TAGS:
                self.skip = (tag, self.skip[1] + 1)
            return
        if tag == "title":
            self.in_title = True
            return
        if tag not in VOID_TAGS and tag != "html" and _should_drop(tag, attrs):
            self.skip = (tag, 1)
            return
        if tag in ("ul", "ol"):
            self.list_depth += 1
        if tag == "table":
            self.tables.append([])
            return
        if tag == "tr" and self.tables:
            self.tables[-1].append([])
            return
        if tag in ("td", "th") and self.tables:
            self.bufs.append([])
            return
        if tag in BLOCK_TAGS:
            self._newline()
        cls = attrs.get("class") or ""
        if RATING_ATTR.search(cls):
            self._emit(f" [{cls.strip()}] ")
        if re.fullmatch(r"h[1-6]", tag):
            self._emit("#" * int(tag[1]) + " ")
        elif tag == "li":
            self._emit("  " * max(self.list_depth - 1, 0) + "- ")
        elif tag == "dd":
            self._emit(": ")
        elif tag in ("s", "del", "strike"):
            self._emit("~~")
        elif tag == "br":
            self._newline()
        elif tag == "img" and attrs.get("alt"):
            self._emit(f" [image: {attrs['alt']}] ")
        elif tag == "a":
            href = (attrs.get("href") or "").strip()
            url = ""
            if href and not href.lower().startswith(("javascript:", "mailto:", "tel:", "#")):
                url = urldefrag(urljoin(self.base, href))[0]
            self.anchors.append({"url": url, "rel": (attrs.get("rel") or "").lower(), "title": attrs.get("title") or ""})
            self.bufs.append([])

    def handle_endtag(self, tag):
        if self.skip:
            if tag == self.skip[0]:
                n = self.skip[1] - 1
                self.skip = (tag, n) if n else None
            return
        if tag == "title":
            self.in_title = False
            return
        if tag in ("ul", "ol"):
            self.list_depth = max(self.list_depth - 1, 0)
        if tag in ("s", "del", "strike"):
            self._emit("~~")
            return
        if tag == "a" and self.anchors:
            a = self.anchors.pop()
            text = _squash("".join(self.bufs.pop()))
            if len(a["title"]) > len(text) and text.rstrip(".… ") and a["title"].startswith(text.rstrip(".… ")):
                text = _squash(a["title"])
            if a["url"]:
                self._emit(f"[{text}]({a['url']})" if text else "")
                if not any(ln["url"] == a["url"] and ln["text"] == text for ln in self.links):
                    self.links.append({"text": text, "url": a["url"], "rel": a["rel"]})
            else:
                self._emit(text)
            return
        if tag in ("td", "th") and self.tables and len(self.bufs) > 1:
            cell = _squash("".join(self.bufs.pop())).replace("|", "/")
            if not self.tables[-1]:
                self.tables[-1].append([])
            self.tables[-1][-1].append(cell)
            return
        if tag == "table" and self.tables:
            self._emit("\n" + _table_md(self.tables.pop()) + "\n")
            return
        if tag in BLOCK_TAGS:
            self._newline()

    def handle_data(self, data):
        if self.skip:
            return
        if self.in_title:
            self.title += data
            return
        self._emit(data)

    def result(self) -> str:
        while len(self.bufs) > 1:
            inner = "".join(self.bufs.pop())
            self._emit(inner)
        return _tidy("".join(self.bufs[0]))


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _table_md(rows: list[list[str]]) -> str:
    rows = [r for r in rows if any(c for c in r)]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)


def _tidy(text: str) -> str:
    out = []
    for line in text.split("\n"):
        indent = len(line) - len(line.lstrip(" "))
        body = re.sub(r"[ \t\r\f\v]+", " ", line.strip())
        if body in ("", "-", ":", "#", "##", "###", "~~~~"):
            continue
        if body.startswith(("#", "| ")) and out and not out[-1].startswith("| ") and out[-1] != "":
            out.append("")
        out.append(" " * min(indent, 6) + body if body.startswith("- ") else body)
    return "\n".join(out).strip()


def clean_html(html: str, base_url: str = "") -> Page:
    parser = _Cleaner(base_url)
    parser.feed(html)
    parser.close()
    return Page(url=base_url, title=_squash(parser.title), markdown=parser.result(), links=parser.links)
