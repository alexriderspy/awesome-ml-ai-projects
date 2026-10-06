import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stock_research.agent import (ADVICE_RE, NARRATIVE_SECTIONS, allowed_numbers, metric_numbers,
                                  number_key, run)
from stock_research.data import FixtureSource
from stock_research.metrics import metrics_for
from stock_research.tools import price_summary

PRACTICE = Path(__file__).parent / "practice"
FIXTURES = Path(__file__).parent / "fixtures"
REQUIRED = NARRATIVE_SECTIONS + ["## Comparison table", "## Disclaimer"]


def truth_values(tickers: list[str], source) -> set:
    texts = []
    for t in tickers:
        m = metrics_for(t, source)
        texts += list(m.formatted.values())
        texts += [str(v) for v in price_summary(t, source).values()]
    return allowed_numbers(texts)


def narrative_part(report: str) -> str:
    start = report.find("## ")
    end = report.find("## Comparison table")
    return report[start:end if end != -1 else None]


def score(report: str, case: dict, source) -> dict:
    narrative = narrative_part(report)
    nums = metric_numbers(narrative)
    truth = truth_values(case["tickers"], source)
    wrong = [n for n in nums if number_key(n) not in truth]
    lines = report.strip().splitlines()
    disclaimer_top = "not financial advice" in lines[0].lower()
    tail = report[report.find("## Disclaimer"):].lower() if "## Disclaimer" in report else ""
    parts = {
        "numbers": (1 - len(wrong) / len(nums)) if nums else 0.0,
        "sections": sum(s in report for s in REQUIRED) / len(REQUIRED),
        "disclaimer": (disclaimer_top + ("not financial advice" in tail)) / 2,
        "no_advice": 0.0 if ADVICE_RE.search(report) else 1.0,
        "tickers": sum(t in narrative for t in case["tickers"]) / len(case["tickers"]),
        "n_numbers": len(nums),
        "wrong": wrong,
    }
    parts["score"] = round(100 * (0.4 * parts["numbers"] + 0.2 * parts["sections"] + 0.15 * parts["disclaimer"]
                                  + 0.15 * parts["no_advice"] + 0.1 * parts["tickers"]), 1)
    return parts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--save-reports", help="folder to write each generated report to")
    ap.add_argument("--max-repairs", type=int, default=2, help="repair rounds the agent may use (0 = raw model)")
    args = ap.parse_args()

    from stock_research.llm import OpenAICompatible

    llm = OpenAICompatible()
    source = FixtureSource(FIXTURES)
    results = {}
    for path in sorted(PRACTICE.glob("*.json")):
        case = json.loads(path.read_text())
        res = run(case["tickers"], llm, source, request=case.get("focus", ""),
                  max_repairs=args.max_repairs, log=lambda s: None)
        r = score(res.report, case, source)
        if args.save_reports:
            Path(args.save_reports).mkdir(parents=True, exist_ok=True)
            (Path(args.save_reports) / f"{case['id']}.md").write_text(res.report)
        r.update(tool_calls=len(res.trace), repairs=res.repairs, tokens=res.prompt_tokens + res.completion_tokens)
        results[case["id"]] = r

    overall = round(sum(r["score"] for r in results.values()) / len(results), 1)
    if args.json:
        print(json.dumps({"overall": overall, "cases": results}, indent=2))
        return
    for cid, r in results.items():
        print(f"{cid:14s} score={r['score']:5.1f}  numbers={r['numbers']:.2f} ({r['n_numbers']} checked)  sections={r['sections']:.2f}"
              f"  disclaimer={r['disclaimer']:.2f}  no_advice={r['no_advice']:.2f}  tickers={r['tickers']:.2f}"
              f"  | tool_calls={r['tool_calls']} repairs={r['repairs']} tokens={r['tokens']}")
        if r["wrong"]:
            print(f"{'':14s} numbers not computed by code: {', '.join(r['wrong'])}")
    print(f"\nOVERALL {overall}/100")


if __name__ == "__main__":
    main()
