import math
import re
from dataclasses import dataclass, field

from .hn import Story
from .llm import ChatModel, parse_json
from .profile import Profile

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#]*(?:\.[a-z0-9]+)*")
BODY_WEIGHT = 0.3
K1, B = 1.2, 0.75


def stem(tok: str) -> str:
    if tok.endswith("'s"):
        tok = tok[:-2]
    if (len(tok) > 3 and "." not in tok and tok.endswith("s") and not tok.endswith(("ss", "is"))
            and not (tok.endswith("us") and len(tok) >= 6)):
        tok = tok[:-1]
    return tok


def tokens(text: str) -> list[str]:
    return [stem(t) for t in TOKEN_RE.findall(text.lower().replace("’", "'"))]


def count_phrase(phrase: list[str], doc: list[str]) -> int:
    n = len(phrase)
    if not n or n > len(doc):
        return 0
    return sum(1 for i in range(len(doc) - n + 1) if doc[i:i + n] == phrase)


def sat(x: float, c: float = 2.0) -> float:
    return 1.0 - math.exp(-x / c)


@dataclass
class Ranked:
    story: Story
    score: float
    matches: dict[str, list[str]] = field(default_factory=dict)
    disliked: list[str] = field(default_factory=list)
    llm_score: float | None = None


class _Fields:
    def __init__(self, s: Story):
        self.title = tokens(f"{s.title} {s.domain}")
        self.body = tokens(" ".join([s.text, s.page_text, *s.top_comments])[:6000])


def _bm25(tf: int, dl: int, avgdl: float, idf: float) -> float:
    if not tf:
        return 0.0
    return idf * tf * (K1 + 1) / (tf + K1 * (1 - B + B * dl / max(avgdl, 1e-9)))


def rank(stories: list[Story], profile: Profile) -> list[Ranked]:
    if not stories:
        return []
    docs = [_Fields(s) for s in stories]
    n = len(docs)
    avg_t = sum(len(d.title) for d in docs) / n
    avg_b = sum(len(d.body) for d in docs) / n or 1.0

    phrases = {kw: tokens(kw) for i in profile.interests for kw in i.keywords}
    phrases.update({kw: tokens(kw) for kw in profile.dislikes})
    idf = {}
    for kw, ph in phrases.items():
        df = sum(1 for d in docs if count_phrase(ph, d.title) or count_phrase(ph, d.body))
        idf[kw] = math.log(1 + (n - df + 0.5) / (df + 0.5))

    def phrase_score(kw: str, d: _Fields) -> float:
        ph = phrases[kw]
        return (_bm25(count_phrase(ph, d.title), len(d.title), avg_t, idf[kw])
                + BODY_WEIGHT * _bm25(count_phrase(ph, d.body), len(d.body), avg_b, idf[kw]))

    max_pts = math.log1p(max(s.score for s in stories)) or 1.0
    max_com = math.log1p(max(s.comments for s in stories)) or 1.0

    out = []
    for s, d in zip(stories, docs):
        total, matches = 0.0, {}
        for it in profile.interests:
            hits = {kw: phrase_score(kw, d) for kw in it.keywords}
            hits = {k: v for k, v in hits.items() if v > 0}
            if hits:
                matches[it.name] = sorted(hits, key=hits.get, reverse=True)
                total += it.weight * sat(sum(hits.values()))
        bad = {kw: phrase_score(kw, d) for kw in profile.dislikes}
        bad = {k: v for k, v in bad.items() if v > 0}
        total -= profile.dislike_weight * sat(sum(bad.values()))
        popularity = 0.5 * math.log1p(s.score) / max_pts + 0.5 * math.log1p(s.comments) / max_com
        total += profile.prior_weight * popularity
        out.append(Ranked(s, round(total, 4), matches, sorted(bad)))
    return sorted(out, key=lambda r: -r.score)


RERANK_SYSTEM = (
    "You rank Hacker News stories for one specific reader. Score each story 0-10 for how much "
    "THIS reader would want to read it (10 = must read, 0 = irrelevant or something they said they don't want). "
    "Judge by the topic, not by popularity. Reply with JSON only: {\"scores\": {\"<id>\": <0-10>, ...}}"
)


def llm_rerank(ranked: list[Ranked], profile: Profile, llm: ChatModel, top_n: int = 15) -> list[Ranked]:
    head, tail = ranked[:top_n], ranked[top_n:]
    if not head:
        return ranked
    lines = []
    for r in head:
        s = r.story
        extra = f" | {s.text[:200]}" if s.text else ""
        lines.append(f"[{s.id}] {s.title} ({s.domain or 'news.ycombinator.com'}){extra}")
    user = f"{profile.describe()}\n\nStories:\n" + "\n".join(lines)
    try:
        scores = parse_json(llm.complete(RERANK_SYSTEM, user)).get("scores", {})
        for r in head:
            v = scores.get(str(r.story.id))
            r.llm_score = float(v) if v is not None else None
    except Exception:
        return ranked
    if all(r.llm_score is None for r in head):
        return ranked
    order = {id(r): i for i, r in enumerate(head)}
    head = sorted(head, key=lambda r: (-(r.llm_score if r.llm_score is not None else -1), order[id(r)]))
    return head + tail
