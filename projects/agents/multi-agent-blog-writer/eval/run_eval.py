import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blog_writer import checks
from blog_writer.search import CachedSearch

PRACTICE = Path(__file__).parent / "practice"


def fact_coverage(post: str, facts: list[dict]) -> float:
    body, _ = checks.split_sources(post)
    text = checks.CITE_RE.sub("", body).lower()
    hit = sum(1 for f in facts if all(any(k.lower() in text for k in group) for group in f["keywords"]))
    return hit / len(facts)


def citation_validity(post: str, search_urls: set[str]) -> float:
    rep = checks.citation_report(post, search_urls)
    listed = checks.parse_sources(post)
    if not rep["cited"] or not listed:
        return 0.0
    mapped = 1 - len(rep["unlisted"]) / len(rep["cited"])
    from_search = 1 - len(rep["not_from_search"]) / len(listed)
    return 0.5 * mapped + 0.5 * from_search


def score(post: str, case: dict, search_urls: set[str]) -> dict:
    s = checks.structure(post)
    parts = {
        "facts": fact_coverage(post, case["facts"]),
        "citations": citation_validity(post, search_urls),
        "structure": sum(s.values()) / len(s),
        "budget": checks.budget_score(checks.word_count(post), case["word_budget"]),
        "words": checks.word_count(post),
    }
    parts["score"] = round(100 * (0.4 * parts["facts"] + 0.3 * parts["citations"]
                                  + 0.15 * parts["structure"] + 0.15 * parts["budget"]), 1)
    return parts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-steps", type=int, default=30)
    args = ap.parse_args()

    from blog_writer.llm import OpenAICompatible
    from blog_writer.team import write_post

    llm = OpenAICompatible()
    results = {}
    for path in sorted(PRACTICE.glob("*.json")):
        case = json.loads(path.read_text())
        search = CachedSearch(case["search_results"])
        res = write_post(case["topic"], llm, word_budget=case["word_budget"], search=search, max_steps=args.max_steps)
        post = res.state.get("final") or res.state.get("draft") or ""
        r = score(post, case, search.returned)
        r.update(steps=res.steps, stopped=res.stopped, revisions=res.state["revisions"],
                 handoffs=sum(e["event"] == "handoff" for e in res.log))
        results[case["id"]] = r

    overall = round(sum(r["score"] for r in results.values()) / len(results), 1)
    if args.json:
        print(json.dumps({"overall": overall, "cases": results}, indent=2))
        return
    for cid, r in results.items():
        print(f"{cid:16s} score={r['score']:5.1f}  facts={r['facts']:.2f}  citations={r['citations']:.2f}  "
              f"structure={r['structure']:.2f}  budget={r['budget']:.2f}  words={r['words']}  "
              f"steps={r['steps']}  handoffs={r['handoffs']}  revisions={r['revisions']}  stopped={r['stopped']}")
    print(f"\nOVERALL {overall}/100")


if __name__ == "__main__":
    main()
