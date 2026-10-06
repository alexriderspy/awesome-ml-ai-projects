import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hn_brief.pipeline import load_snapshot
from hn_brief.profile import load_profile
from hn_brief.rank import llm_rerank, rank, tokens
from hn_brief.summarize import Entry, sentences, summarize_all

PRACTICE = Path(__file__).parent / "practice"
STOP = set("a an the and or of in on for to with by from at is are was be as its it this that how why what we you "
           "your our my just now new into vs than after before about can show ask hn pdf".split())
MAX_SUMMARY_WORDS, MAX_WHY_WORDS = 66, 30


def ndcg_at_k(ranked_ids: list[int], gold: dict[int, int], k: int = 5) -> float:
    dcg = sum((2 ** gold.get(i, 0) - 1) / math.log2(n + 2) for n, i in enumerate(ranked_ids[:k]))
    ideal = sorted(gold.values(), reverse=True)[:k]
    idcg = sum((2 ** g - 1) / math.log2(n + 2) for n, g in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def format_ok(summary: str, why: str) -> float:
    s_ok = 1 <= len(sentences(summary)) <= 3 and len(summary.split()) <= MAX_SUMMARY_WORDS
    w_ok = bool(why) and len(sentences(why)) == 1 and len(why.split()) <= MAX_WHY_WORDS
    return 0.5 * s_ok + 0.5 * w_ok


def key_terms(title: str, n: int = 4) -> list[str]:
    seen = []
    for t in tokens(title):
        if t not in STOP and len(t) >= 3 and not t.isdigit() and t not in seen:
            seen.append(t)
    return sorted(seen, key=len, reverse=True)[:n]


def term_coverage(summary: str, title: str) -> float:
    terms = key_terms(title)
    if not terms:
        return 1.0
    have = set(tokens(summary))
    return sum(t in have for t in terms) / len(terms)


def load_cases() -> list[dict]:
    meta = json.loads((PRACTICE / "labels.json").read_text())
    cases = []
    for prof, sets in meta["labels"].items():
        for set_name, gold in sets.items():
            cases.append({
                "id": f"{prof}/{set_name}",
                "profile": load_profile(PRACTICE / "profiles" / f"{prof}.yaml"),
                "stories": load_snapshot(PRACTICE / meta["sets"][set_name]),
                "gold": {int(k): v for k, v in gold.items()},
            })
    return cases


def score_entries(entries: list[Entry]) -> tuple[float, float]:
    if not entries:
        return 0.0, 0.0
    fmt = sum(format_ok(e.summary, e.why) for e in entries) / len(entries)
    terms = sum(term_coverage(e.summary, e.ranked.story.title) for e in entries) / len(entries)
    return fmt, terms


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=5, help="NDCG cutoff")
    ap.add_argument("--summaries", type=int, default=3, help="stories to summarize per case")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    llm = None
    if not args.no_llm:
        from hn_brief.llm import OpenAICompatible

        llm = OpenAICompatible()

    results = {}
    for c in load_cases():
        ranked = rank(c["stories"], c["profile"])
        r = {"ndcg_bm25": ndcg_at_k([x.story.id for x in ranked], c["gold"], args.k)}
        if llm is None:
            r["score"] = round(100 * r["ndcg_bm25"], 1)
        else:
            reranked = llm_rerank(list(ranked), c["profile"], llm)
            r["ndcg_llm"] = ndcg_at_k([x.story.id for x in reranked], c["gold"], args.k)
            entries = summarize_all(reranked[: args.summaries], c["profile"], llm)
            r["format"], r["terms"] = score_entries(entries)
            r["score"] = round(100 * (0.5 * r["ndcg_llm"] + 0.3 * r["format"] + 0.2 * r["terms"]), 1)
        results[c["id"]] = r

    overall = round(sum(r["score"] for r in results.values()) / len(results), 1)
    mean = lambda key: sum(r[key] for r in results.values()) / len(results)
    if args.json:
        print(json.dumps({"overall": overall, "cases": results}, indent=2))
        return
    for cid, r in results.items():
        line = f"{cid:34s} score={r['score']:5.1f}  ndcg@{args.k}_bm25={r['ndcg_bm25']:.2f}"
        if llm is not None:
            line += f"  ndcg@{args.k}_llm={r['ndcg_llm']:.2f}  format={r['format']:.2f}  terms={r['terms']:.2f}"
        print(line)
    print(f"\nmean NDCG@{args.k}: bm25={mean('ndcg_bm25'):.3f}" + (f"  llm_rerank={mean('ndcg_llm'):.3f}" if llm else ""))
    print(f"OVERALL {overall}/100")


if __name__ == "__main__":
    main()
