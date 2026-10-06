import re
from dataclasses import dataclass, field
from pathlib import Path

MUST_RE = re.compile(r"must|required|requirements|essential", re.I)
NICE_RE = re.compile(r"nice|bonus|preferred|plus|desirable", re.I)
BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.*\S)")
RESUME_EXTS = {".md", ".txt"}


@dataclass
class Requirement:
    id: str
    text: str
    must: bool


@dataclass
class JobDescription:
    title: str
    text: str
    requirements: list[Requirement]
    panel: str = ""

    def requirement_lines(self) -> str:
        return "\n".join(f"{r.id} ({'must-have' if r.must else 'nice-to-have'}): {r.text}" for r in self.requirements)


@dataclass
class Resume:
    candidate_id: str
    text: str
    meta: dict = field(default_factory=dict)


def parse_jd(text: str) -> JobDescription:
    title, panel, section = "", "", None
    must, nice = [], []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            head = s.lstrip("#").strip()
            if not title and s.startswith("# "):
                title = head
            section = "must" if MUST_RE.search(head) else "nice" if NICE_RE.search(head) else None
            continue
        if s.lower().startswith("panel:"):
            panel = s.split(":", 1)[1].strip().lower()
            continue
        m = BULLET_RE.match(line)
        if m and section:
            (must if section == "must" else nice).append(m.group(1))
    reqs = [Requirement(f"M{i}", t, True) for i, t in enumerate(must, 1)]
    reqs += [Requirement(f"N{i}", t, False) for i, t in enumerate(nice, 1)]
    if not reqs:
        raise ValueError("No requirements found. Put them as bullets under '## Must have' / '## Nice to have'.")
    return JobDescription(title or "Untitled role", text, reqs, panel)


def load_jd(path: str | Path) -> JobDescription:
    return parse_jd(Path(path).read_text(encoding="utf-8"))


def load_resumes(folder: str | Path) -> list[Resume]:
    files = sorted(p for p in Path(folder).iterdir() if p.suffix.lower() in RESUME_EXTS)
    if not files:
        raise ValueError(f"No .md/.txt resumes in {folder}")
    return [Resume(p.stem, p.read_text(encoding="utf-8")) for p in files]
