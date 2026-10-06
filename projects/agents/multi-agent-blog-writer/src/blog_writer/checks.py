import re

CITE_RE = re.compile(r"\[(\d{1,3})\]")
SOURCE_LINE_RE = re.compile(r"^\s*\[(\d{1,3})\]\s*(.*?)\s*[—-]\s*<?(https?://\S+?)>?\s*$")
CONCLUSION_WORDS = ("conclusion", "takeaway", "wrapping up", "final thoughts", "summary", "bottom line")


def split_sources(post: str) -> tuple[str, str]:
    m = re.search(r"(?im)^##\s+sources\s*$", post)
    if not m:
        return post, ""
    return post[: m.start()], post[m.end():]


def parse_sources(post: str) -> dict[int, str]:
    _, block = split_sources(post)
    out = {}
    for line in block.splitlines():
        m = SOURCE_LINE_RE.match(line)
        if m:
            out[int(m.group(1))] = m.group(3)
    return out


def cited_ids(post: str) -> list[int]:
    body, _ = split_sources(post)
    return [int(n) for n in CITE_RE.findall(body)]


def word_count(post: str) -> int:
    body, _ = split_sources(post)
    body = CITE_RE.sub("", body)
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", body))


def structure(post: str) -> dict[str, bool]:
    body, sources = split_sources(post)
    lines = body.strip().splitlines()
    headings = [l[3:].strip().lower() for l in lines if l.startswith("## ")]
    title = bool(lines) and lines[0].startswith("# ")
    first_h2 = next((i for i, l in enumerate(lines) if l.startswith("## ")), len(lines))
    intro = any(l.strip() and not l.startswith("#") for l in lines[1:first_h2])
    conclusion = bool(headings) and any(w in headings[-1] for w in CONCLUSION_WORDS)
    sections = [h for h in headings if not any(w in h for w in CONCLUSION_WORDS)]
    return {
        "title": title,
        "intro": intro,
        "sections": len(sections) >= 2,
        "conclusion": conclusion,
        "sources": bool(parse_sources(post)),
    }


def citation_report(post: str, search_urls: set[str]) -> dict:
    cited = set(cited_ids(post))
    listed = parse_sources(post)
    return {
        "cited": sorted(cited),
        "unlisted": sorted(cited - listed.keys()),
        "not_from_search": sorted(n for n, u in listed.items() if u not in search_urls),
        "uncited": sorted(listed.keys() - cited),
    }


def budget_score(words: int, budget: int) -> float:
    lo, hi = 0.75 * budget, 1.15 * budget
    if lo <= words <= hi:
        return 1.0
    gap = (lo - words) if words < lo else (words - hi)
    return max(0.0, 1 - gap / (0.5 * budget))


def editor_report(post: str, budget: int, search_urls: set[str]) -> str:
    s = structure(post)
    c = citation_report(post, search_urls)
    words = word_count(post)
    problems = [f"missing {k}" for k, ok in s.items() if not ok]
    if not c["cited"]:
        problems.append("no inline citations like [1]")
    if c["unlisted"]:
        problems.append(f"citations with no source: {c['unlisted']}")
    if c["not_from_search"]:
        problems.append(f"sources not from search results: {c['not_from_search']}")
    if budget_score(words, budget) < 1:
        problems.append(f"length {words} words, target {int(0.75 * budget)}-{int(1.15 * budget)}")
    head = f"words={words} (budget {budget}); structure={s}; cited={c['cited']}"
    return head + ("\nPROBLEMS: " + "; ".join(problems) if problems else "\nNo problems found.")
