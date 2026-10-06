import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from issue_triage import Snapshot, cost_usd, default_prices, triage

GOLD = Path(__file__).parent / "gold.json"
WEIGHTS = {"labels": 0.4, "duplicates": 0.3, "replies": 0.2, "efficiency": 0.1}
TOKENS_FULL, TOKENS_ZERO = 15_000, 60_000
REPRO_RE = re.compile(r"reproduc|steps|version", re.I)


def load_gold(path: Path = GOLD) -> dict:
    g = json.loads(path.read_text())
    return {"labels": {int(k): set(v) for k, v in g["labels"].items()},
            "dupes": {d["issue"]: d["duplicate_of"] for d in g["duplicates"]}}


def label_scores(pred: dict[int, set], gold: dict[int, set]) -> dict:
    tp = sum(len(pred[n] & gold[n]) for n in pred)
    fp = sum(len(pred[n] - gold[n]) for n in pred)
    fn = sum(len(gold[n] - pred[n]) for n in pred)
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0.0,
            "exact": sum(pred[n] == gold[n] for n in pred) / max(1, len(pred))}


def dup_scores(pred: dict[int, int | None], gold_dupes: dict[int, int]) -> dict:
    gold_pairs = {frozenset(p) for p in gold_dupes.items()}
    pred_pairs = {frozenset((n, d)) for n, d in pred.items() if d}
    relevant = {frozenset((n, d)) for n, d in gold_dupes.items() if n in pred}
    tp = len(pred_pairs & gold_pairs)
    p = tp / len(pred_pairs) if pred_pairs else (1.0 if not relevant else 0.0)
    r = len(pred_pairs & relevant) / len(relevant) if relevant else 1.0
    return {"precision": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0.0,
            "predicted": len(pred_pairs), "gold": len(relevant)}


def reply_score(reply: str, gold_labels: set, gold_dup: int | None) -> float:
    if len(reply.split()) < 10:
        return 0.0
    checks = []
    if gold_dup:
        checks.append(f"#{gold_dup}" in reply)
    if "needs-repro" in gold_labels:
        checks.append(bool(REPRO_RE.search(reply)))
    return sum(checks) / len(checks) if checks else 1.0


def efficiency(avg_tokens: float) -> float:
    return max(0.0, min(1.0, (TOKENS_ZERO - avg_tokens) / (TOKENS_ZERO - TOKENS_FULL)))


def score_run(results: list[dict], gold: dict) -> dict:
    pred_labels = {r["number"]: set(r["labels"]) for r in results}
    labels = label_scores(pred_labels, gold["labels"])
    dupes = dup_scores({r["number"]: r["duplicate_of"] for r in results}, gold["dupes"])
    replies = [reply_score(r["reply"], gold["labels"][r["number"]], gold["dupes"].get(r["number"])) for r in results]
    drafted = sum(len(r["reply"].split()) >= 10 for r in results) / len(results)
    tokens = [r["prompt_tokens"] + r["completion_tokens"] for r in results]
    avg_tokens = sum(tokens) / len(tokens)
    parts = {"labels": labels["f1"], "duplicates": dupes["f1"], "replies": sum(replies) / len(replies),
             "efficiency": efficiency(avg_tokens)}
    overall = round(100 * sum(WEIGHTS[k] * v for k, v in parts.items()), 1)
    return {"overall": overall, "parts": parts, "labels": labels, "duplicates": dupes, "drafted_rate": drafted,
            "avg_prompt_tokens": sum(r["prompt_tokens"] for r in results) / len(results),
            "avg_completion_tokens": sum(r["completion_tokens"] for r in results) / len(results),
            "reply_scores": replies}


def case_line(r: dict, gold: dict, reply_s: float) -> str:
    n = r["number"]
    g, p = gold["labels"][n], set(r["labels"])
    gd, pd = gold["dupes"].get(n), r["duplicate_of"]
    lab = "ok  " if p == g else "MISS"
    dup = "ok  " if gd == pd or (pd and gold["dupes"].get(pd) == n) else "MISS"
    return (f"#{n:<3} labels {lab} {','.join(sorted(p)) or '-':28s} gold {','.join(sorted(g)):28s} "
            f"dup {dup} {('#' + str(pd)) if pd else '-':4s} gold {('#' + str(gd)) if gd else '-':4s} "
            f"reply={reply_s:.2f} steps={r['steps']:<2d} tokens={r['prompt_tokens'] + r['completion_tokens']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="only the first N untriaged issues")
    ap.add_argument("--all", action="store_true", help="all 60 issues (own labels hidden)")
    ap.add_argument("--max-steps", type=int, default=10)
    ap.add_argument("--price-in", type=float, help="USD per 1M prompt tokens (default PRICE_IN_PER_M)")
    ap.add_argument("--price-out", type=float, help="USD per 1M completion tokens (default PRICE_OUT_PER_M)")
    ap.add_argument("--save", help="also write the raw results JSON here")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    from issue_triage.llm import OpenAICompatible

    snap, gold, llm = Snapshot.load(), load_gold(), OpenAICompatible()
    numbers = sorted(snap.issues) if args.all else snap.untriaged()
    if args.limit:
        numbers = numbers[: args.limit]
    results = [triage(n, snap, llm, max_steps=args.max_steps).to_dict() for n in numbers]
    if args.save:
        Path(args.save).write_text(json.dumps(results, indent=2, ensure_ascii=False))
    s = score_run(results, gold)
    pin, pout = default_prices()
    pin = args.price_in if args.price_in is not None else pin
    pout = args.price_out if args.price_out is not None else pout
    usd = cost_usd(s["avg_prompt_tokens"], s["avg_completion_tokens"], pin, pout)

    if args.json:
        print(json.dumps({**s, "usd_per_issue": usd, "cases": results}, indent=2, default=list))
        return
    for r, rs in zip(results, s["reply_scores"]):
        print(case_line(r, gold, rs))
    lb, dp = s["labels"], s["duplicates"]
    print(f"\nissues           {len(results)}")
    print(f"labels           micro-P={lb['precision']:.3f} micro-R={lb['recall']:.3f} "
          f"micro-F1={lb['f1']:.3f} exact-match={lb['exact']:.3f}")
    print(f"duplicates       P={dp['precision']:.3f} R={dp['recall']:.3f} F1={dp['f1']:.3f} "
          f"(predicted {dp['predicted']}, gold {dp['gold']})")
    print(f"replies          drafted={s['drafted_rate']:.3f} checks={s['parts']['replies']:.3f}")
    print(f"cost per issue   prompt={s['avg_prompt_tokens']:.0f} completion={s['avg_completion_tokens']:.0f} "
          f"tokens  ${usd:.5f} (at ${pin}/M in, ${pout}/M out)")
    print("score parts      " + "  ".join(f"{k}={v:.3f}x{WEIGHTS[k]}" for k, v in s["parts"].items()))
    print(f"\nOVERALL {s['overall']}/100")


if __name__ == "__main__":
    main()
