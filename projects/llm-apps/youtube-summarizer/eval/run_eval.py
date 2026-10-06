import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from yt_summarizer.summarize import summarize
from yt_summarizer.transcript import Segment, parse_ts

PRACTICE = Path(__file__).parent / "practice"
TS_RE = re.compile(r"\[(\d{1,2}(?::\d{2}){1,2})\]")
SECTIONS = ("## TL;DR", "## Key points", "## Chapters")


def fact_coverage(summary: str, facts: list[dict]) -> float:
    text = summary.lower()
    hit = 0
    for f in facts:
        if all(any(k.lower() in text for k in group) for group in f["keywords"]):
            hit += 1
    return hit / len(facts)


def timestamp_truth(summary: str, segments: list[Segment], tolerance: int = 2) -> float:
    cited = [parse_ts(t) for t in TS_RE.findall(summary)]
    if not cited:
        return 0.0
    starts = [int(s.start) for s in segments]
    ok = sum(1 for c in cited if any(abs(c - s) <= tolerance for s in starts))
    return ok / len(cited)


def score(summary: str, case: dict, max_words: int) -> dict:
    segments = [Segment(s["start"], s["text"]) for s in case["segments"]]
    words = len(summary.split())
    parts = {
        "facts": fact_coverage(summary, case["facts"]),
        "timestamps": timestamp_truth(summary, segments),
        "length": 1.0 if words <= max_words * 1.1 else max(0.0, 1 - (words - max_words) / max_words),
        "structure": sum(s in summary for s in SECTIONS) / len(SECTIONS),
    }
    parts["score"] = round(100 * (0.5 * parts["facts"] + 0.3 * parts["timestamps"] + 0.1 * parts["length"] + 0.1 * parts["structure"]), 1)
    return parts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-words", type=int, default=250)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    from yt_summarizer.llm import OpenAICompatible

    llm = OpenAICompatible()
    results = {}
    for path in sorted(PRACTICE.glob("*.json")):
        case = json.loads(path.read_text())
        segs = [Segment(s["start"], s["text"]) for s in case["segments"]]
        results[case["id"]] = score(summarize(segs, llm, max_words=args.max_words), case, args.max_words)

    overall = round(sum(r["score"] for r in results.values()) / len(results), 1)
    if args.json:
        print(json.dumps({"overall": overall, "cases": results}, indent=2))
        return
    for cid, r in results.items():
        print(f"{cid:16s} score={r['score']:5.1f}  facts={r['facts']:.2f}  timestamps={r['timestamps']:.2f}  length={r['length']:.2f}  structure={r['structure']:.2f}")
    print(f"\nOVERALL {overall}/100")


if __name__ == "__main__":
    main()
