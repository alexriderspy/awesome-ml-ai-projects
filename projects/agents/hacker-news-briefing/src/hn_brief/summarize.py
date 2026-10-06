import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from .llm import ChatModel, parse_json
from .profile import Profile
from .rank import Ranked

SYSTEM = (
    "You write one entry of a personal Hacker News morning brief. Use only the material given; "
    "if you only have the title, describe what the title says and do not invent details. "
    "Reply with JSON only: {\"summary\": \"...\", \"why\": \"...\"}.\n"
    "- summary: 1 to 3 short sentences, at most 60 words, plain English, and it must use the key "
    "terms from the title (names, products, technologies).\n"
    "- why: ONE sentence, at most 25 words, telling this reader why it matters to them specifically, "
    "based on their interests. Address them as 'you'."
)
SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


@dataclass
class Entry:
    ranked: Ranked
    summary: str
    why: str


def sentences(text: str) -> list[str]:
    text = text.strip()
    return [s for s in SENT_RE.split(text) if s.strip()] if text else []


def story_material(r: Ranked, max_chars: int = 2500) -> str:
    s = r.story
    parts = [f"Title: {s.title}", f"Link: {s.url or s.hn_url}", f"Points: {s.score}, comments: {s.comments}"]
    if s.text:
        parts.append(f"Post text: {s.text[:1200]}")
    if s.page_text:
        parts.append(f"Linked page (excerpt): {s.page_text[:1500]}")
    for i, c in enumerate(s.top_comments, 1):
        parts.append(f"Top comment {i}: {c[:400]}")
    return "\n".join(parts)[:max_chars]


def summarize_one(r: Ranked, profile: Profile, llm: ChatModel) -> Entry:
    matched = "; ".join(f"{k}: {', '.join(v)}" for k, v in r.matches.items()) or "none"
    user = f"{profile.describe()}\n\nMatched interests: {matched}\n\n{story_material(r)}"
    raw = llm.complete(SYSTEM, user)
    try:
        d = parse_json(raw)
        summary, why = str(d.get("summary", "")).strip(), str(d.get("why", "")).strip()
    except ValueError:
        summary, why = " ".join(sentences(raw)[:3]), ""
    if not summary:
        summary = r.story.title
    return Entry(r, summary, why)


def summarize_all(chosen: list[Ranked], profile: Profile, llm: ChatModel, workers: int = 4) -> list[Entry]:
    with ThreadPoolExecutor(workers) as pool:
        return list(pool.map(lambda r: summarize_one(r, profile, llm), chosen))
