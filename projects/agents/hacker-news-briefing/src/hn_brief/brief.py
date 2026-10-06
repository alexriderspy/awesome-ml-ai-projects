from datetime import date, datetime, timezone
from pathlib import Path

from .profile import Profile
from .rank import Ranked
from .summarize import Entry


def render(entries: list[Entry], profile: Profile, day: date, pool_size: int, stage: str,
           also: list[Ranked] | None = None) -> str:
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    out = [f"# Hacker News brief - {day.isoformat()}", "",
           f"_For {profile.name} · top {len(entries)} of {pool_size} front-page stories · ranked by {stage} · generated {now}_", ""]
    for n, e in enumerate(entries, 1):
        s = e.ranked.story
        meta = [f"`{s.domain or 'news.ycombinator.com'}`", f"{s.score} points",
                f"[{s.comments} comments]({s.hn_url})"]
        if e.ranked.matches:
            meta.append("matched: " + ", ".join(f"{k} ({', '.join(v[:2])})" for k, v in e.ranked.matches.items()))
        out += [f"## {n}. [{s.title}]({s.url or s.hn_url})", "", " · ".join(meta), "", e.summary, ""]
        if e.why:
            out += [f"**Why it matters to you:** {e.why}", ""]
    if also:
        out += ["## Also on the front page", ""]
        out += [f"- [{r.story.title}]({r.story.url or r.story.hn_url}) ({r.story.score} points)" for r in also]
        out.append("")
    return "\n".join(out)


def write(markdown: str, out_dir: str | Path, day: date) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{day.isoformat()}.md"
    path.write_text(markdown)
    return path


def to_slack_text(entries: list[Entry], day: date) -> str:
    lines = [f"*Hacker News brief - {day.isoformat()}*"]
    for n, e in enumerate(entries, 1):
        s = e.ranked.story
        lines.append(f"{n}. <{s.url or s.hn_url}|{s.title}> ({s.score} pts, <{s.hn_url}|{s.comments} comments>)")
        lines.append(f"    {e.summary}")
        if e.why:
            lines.append(f"    _Why: {e.why}_")
    return "\n".join(lines)
