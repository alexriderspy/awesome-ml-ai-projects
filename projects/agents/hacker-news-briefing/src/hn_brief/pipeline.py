import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .brief import render
from .hn import HNClient, Story
from .llm import ChatModel
from .profile import Profile
from .rank import Ranked, llm_rerank, rank
from .summarize import Entry, summarize_all


@dataclass
class RunResult:
    markdown: str
    entries: list[Entry]
    ranked: list[Ranked]
    log: list[str] = field(default_factory=list)


def load_snapshot(path: str | Path) -> list[Story]:
    data = json.loads(Path(path).read_text())
    return [Story.from_item(i) for i in data["items"]]


def save_snapshot(stories: list[Story], path: str | Path) -> None:
    items = [{"id": s.id, "type": "story", "title": s.title, "url": s.url, "score": s.score,
              "descendants": s.comments, "by": s.by, "time": s.time, **({"text": s.text} if s.text else {})}
             for s in stories]
    Path(path).write_text(json.dumps({"items": items}, indent=1, ensure_ascii=False) + "\n")


def run(profile: Profile, llm: ChatModel, *, client: HNClient | None = None, stories: list[Story] | None = None,
        top_k: int = 5, pool: int = 60, rerank: bool = False, rerank_n: int = 15,
        comments: bool = False, pages: bool = False, day: date | None = None, also: int = 5) -> RunResult:
    day = day or date.today()
    log = []
    if stories is None:
        client = client or HNClient()
        stories = client.top_stories(pool)
        log.append(f"fetched {len(stories)} stories from the HN API (asked for top {pool})")
    else:
        log.append(f"{'fetched' if client else 'loaded'} {len(stories)} stories ({'HN API' if client else 'snapshot'})")

    ranked = rank(stories, profile)
    log.append("stage 1 (BM25 keywords): " + ", ".join(f"{r.story.id}={r.score:.2f}" for r in ranked[:top_k]))
    stage = "BM25 keyword match"
    if rerank:
        ranked = llm_rerank(ranked, profile, llm, top_n=rerank_n)
        stage += f" + LLM rerank of top {rerank_n}"
        log.append("stage 2 (LLM rerank): " + ", ".join(f"{r.story.id}={r.llm_score}" for r in ranked[:top_k]))

    chosen = ranked[:top_k]
    if client and (comments or pages):
        client.enrich([r.story for r in chosen], comments=comments, pages=pages)
        got_c = sum(1 for r in chosen if r.story.top_comments)
        got_p = sum(1 for r in chosen if r.story.page_text)
        log.append(f"enriched shortlist: comments for {got_c}/{len(chosen)}, page text for {got_p}/{len(chosen)}")

    entries = summarize_all(chosen, profile, llm)
    log.append(f"summarized {len(entries)} stories")
    md = render(entries, profile, day, len(stories), stage, also=ranked[top_k:top_k + also])
    return RunResult(md, entries, ranked, log)
