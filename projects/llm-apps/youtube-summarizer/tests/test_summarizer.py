import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from run_eval import fact_coverage, score, timestamp_truth
from yt_summarizer.summarize import summarize
from yt_summarizer.transcript import Segment, chunk, fmt_ts, parse_ts, video_id


class FakeLLM:
    def __init__(self):
        self.calls = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if "merge notes" in system:
            return "## TL;DR\nVectors.\n\n## Key points\n- Embeddings become vectors [00:14]\n\n## Chapters\n[00:00] Intro"
        return "- an idea [00:00]"


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=xDQL3vWwcp0",
        "https://youtu.be/xDQL3vWwcp0?si=abc",
        "https://www.youtube.com/shorts/xDQL3vWwcp0",
        "xDQL3vWwcp0",
    ],
)
def test_video_id(url):
    assert video_id(url) == "xDQL3vWwcp0"


def test_video_id_rejects_garbage():
    with pytest.raises(ValueError):
        video_id("https://example.com/watch")


def test_timestamps_roundtrip():
    assert fmt_ts(65) == "01:05"
    assert fmt_ts(3725) == "1:02:05"
    assert parse_ts("01:05") == 65
    assert parse_ts("1:02:05") == 3725


def test_chunk_respects_size_and_keeps_timestamps():
    segs = [Segment(i * 10.0, "word " * 20) for i in range(50)]
    chunks = chunk(segs, max_chars=500)
    assert len(chunks) > 1
    assert all(len(c) <= 600 for c in chunks)
    assert chunks[0].startswith("[00:00]")


def test_map_reduce_calls_llm_once_per_chunk_plus_merge():
    segs = [Segment(i * 10.0, "word " * 20) for i in range(50)]
    llm = FakeLLM()
    out = summarize(segs, llm, chunk_chars=500)
    assert len(llm.calls) == len(chunk(segs, max_chars=500)) + 1
    assert out.startswith("## TL;DR")


def test_empty_transcript_raises():
    with pytest.raises(ValueError):
        summarize([], FakeLLM())


def test_scorer_rewards_real_timestamps_and_facts():
    case = json.loads((ROOT / "eval/practice/vector-dbs.json").read_text())
    segs = [Segment(s["start"], s["text"]) for s in case["segments"]]
    good = "## TL;DR\nx\n## Key points\n- embedding vector [00:14]\n- cosine [00:56]\n## Chapters\n[00:00] Intro"
    bad = "## TL;DR\nx\n- something [59:59]"
    assert timestamp_truth(good, segs) == 1.0
    assert timestamp_truth(bad, segs) == 0.0
    assert fact_coverage(good, case["facts"]) == pytest.approx(2 / 5)
    assert score(good, case, 250)["score"] > score(bad, case, 250)["score"]
