import re
from dataclasses import dataclass

_ID_PATTERNS = [
    r"(?:v=)([A-Za-z0-9_-]{11})",
    r"(?:youtu\.be/)([A-Za-z0-9_-]{11})",
    r"(?:shorts/|embed/|live/)([A-Za-z0-9_-]{11})",
]


@dataclass
class Segment:
    start: float
    text: str


def video_id(url_or_id: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url_or_id):
        return url_or_id
    for pat in _ID_PATTERNS:
        m = re.search(pat, url_or_id)
        if m:
            return m.group(1)
    raise ValueError(f"Not a YouTube URL or video id: {url_or_id!r}")


def fetch_transcript(url_or_id: str, languages: tuple[str, ...] = ("en", "en-US", "en-GB", "hi")) -> list[Segment]:
    from youtube_transcript_api import YouTubeTranscriptApi

    vid = video_id(url_or_id)
    api = YouTubeTranscriptApi()
    if hasattr(api, "fetch"):
        raw = [{"start": s.start, "text": s.text} for s in api.fetch(vid, languages=list(languages))]
    else:
        raw = YouTubeTranscriptApi.get_transcript(vid, languages=list(languages))
    return [Segment(float(r["start"]), r["text"].replace("\n", " ").strip()) for r in raw if r["text"].strip()]


def fmt_ts(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def parse_ts(ts: str) -> int:
    parts = [int(p) for p in ts.split(":")]
    total = 0
    for p in parts:
        total = total * 60 + p
    return total


def chunk(segments: list[Segment], max_chars: int = 6000) -> list[str]:
    chunks, buf, size = [], [], 0
    for seg in segments:
        line = f"[{fmt_ts(seg.start)}] {seg.text}"
        if buf and size + len(line) > max_chars:
            chunks.append("\n".join(buf))
            buf, size = [], 0
        buf.append(line)
        size += len(line) + 1
    if buf:
        chunks.append("\n".join(buf))
    return chunks
