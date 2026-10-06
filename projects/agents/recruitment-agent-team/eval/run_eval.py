import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from recruit_team.documents import Resume, load_jd, load_resumes
from recruit_team.redact import redact
from recruit_team.scheduler import Calendar, run_scheduler
from recruit_team.screener import screen_all, screen_one

PRACTICE = Path(__file__).parent / "practice"
WEIGHTS = {"f1": 50, "quotes": 25, "schedule": 15, "fairness": 10}
FIT_TOLERANCE = 10.0


def prf(pred: set, gold: set) -> tuple[float, float, float]:
    if not pred and not gold:
        return 1.0, 1.0, 1.0
    tp = len(pred & gold)
    p = tp / len(pred) if pred else 0.0
    r = tp / len(gold) if gold else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def quote_validity(results) -> tuple[float, int, int]:
    valid = sum(r.quotes_final[0] for r in results)
    total = sum(r.quotes_final[1] for r in results)
    return (valid / total if total else 1.0), valid, total


def schedule_score(calendar: Calendar, candidates: list[str], panel: str) -> float:
    if calendar.conflicts():
        return 0.0
    if not candidates:
        return 1.0
    ok = 0
    for c in candidates:
        mine = [b for b in calendar.bookings if b.get("candidate") == c]
        if len(mine) != 1:
            continue
        b = mine[0]
        on_panel = not panel or panel in calendar.interviewers[b["interviewer"]].get("panels", [])
        if on_panel and calendar._available(b["interviewer"], datetime.fromisoformat(b["start"]),
                                            datetime.fromisoformat(b["end"])):
            ok += 1
    return ok / len(candidates)


def fairness_check(llm, jd, case_dir: Path, results) -> tuple[float, list[dict]]:
    by_id = {r.candidate_id: r for r in results}
    checks = []
    for twin_path in sorted((case_dir / "counterfactual").glob("*.md")):
        cid = twin_path.stem
        orig = (case_dir / "resumes" / f"{cid}.md").read_text()
        twin = twin_path.read_text()
        same_text = redact(orig).text == redact(twin).text
        twin_res = screen_one(llm, jd, Resume(cid, twin))
        a = by_id[cid]
        same_decision = twin_res.qualifies == a.qualifies and abs(twin_res.fit - a.fit) <= FIT_TOLERANCE
        checks.append({"candidate": cid, "same_redacted_text": same_text, "fit": a.fit, "twin_fit": twin_res.fit,
                       "pass": same_text and same_decision})
    if not checks:
        return 1.0, []
    return sum(c["pass"] for c in checks) / len(checks), checks


def run_case(llm, case_dir: Path, fairness: bool) -> dict:
    jd = load_jd(case_dir / "jd.md")
    gold = set(json.loads((case_dir / "gold.json").read_text())["shortlist"])
    results = screen_all(llm, jd, load_resumes(case_dir / "resumes"))
    picked = [r.candidate_id for r in results if r.shortlisted]
    p, r, f1 = prf(set(picked), gold)
    qv, qn, qt = quote_validity(results)
    first_v = sum(x.quotes_first[0] for x in results)
    first_t = sum(x.quotes_first[1] for x in results)

    cal = Calendar.load(PRACTICE / "calendar.json")
    sched = run_scheduler(llm, cal, picked, panel=jd.panel, role=jd.title)
    out = {"precision": p, "recall": r, "f1": f1, "quotes": qv, "quotes_valid": qn, "quotes_total": qt,
           "quotes_first_try": first_v / first_t if first_t else 1.0, "schedule": schedule_score(cal, picked, jd.panel),
           "schedule_steps": sched.steps, "shortlist": picked, "gold": sorted(gold),
           "retries": sum(x.attempts > 1 for x in results)}
    weights = dict(WEIGHTS)
    if fairness:
        out["fairness"], out["fairness_checks"] = fairness_check(llm, jd, case_dir, results)
    else:
        weights.pop("fairness")
    out["score"] = round(100 * sum(w * out[k] for k, w in weights.items()) / sum(weights.values()), 1)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="", help="comma-separated case folder names (default: all)")
    ap.add_argument("--no-fairness", action="store_true", help="skip the counterfactual re-screen with the model")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    from recruit_team.llm import OpenAICompatible

    llm = OpenAICompatible()
    names = [c for c in args.cases.split(",") if c] or sorted(p.name for p in PRACTICE.iterdir() if (p / "jd.md").exists())
    results = {name: run_case(llm, PRACTICE / name, not args.no_fairness) for name in names}
    overall = round(sum(r["score"] for r in results.values()) / len(results), 1)
    if args.json:
        print(json.dumps({"overall": overall, "cases": results, "usage": llm.usage}, indent=2))
        return
    for name, r in results.items():
        fair = f"  fairness={r['fairness']:.2f}" if "fairness" in r else ""
        print(f"{name:18s} score={r['score']:5.1f}  f1={r['f1']:.2f} (p={r['precision']:.2f} r={r['recall']:.2f})  "
              f"quotes={r['quotes']:.2f} ({r['quotes_valid']}/{r['quotes_total']}, first try {r['quotes_first_try']:.2f})  "
              f"schedule={r['schedule']:.2f}{fair}")
        print(f"{'':18s} shortlist={r['shortlist']} gold={r['gold']}")
        for c in r.get("fairness_checks", []):
            print(f"{'':18s} counterfactual {c['candidate']}: same redacted text={c['same_redacted_text']}, "
                  f"fit {c['fit']} vs twin {c['twin_fit']}")
    cost = llm.cost_usd()
    print(f"\nLLM calls: {llm.usage['calls']}, tokens in/out: {llm.usage['input_tokens']}/{llm.usage['output_tokens']}"
          + (f", est. cost ${cost:.4f}" if cost is not None else ""))
    print(f"\nOVERALL {overall}/100")


if __name__ == "__main__":
    main()
