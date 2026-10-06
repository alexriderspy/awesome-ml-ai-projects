import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from extractor.compare import f1, field_counts, item_match, str_match, value_match
from extractor.extract import extract

PRACTICE = Path(__file__).parent / "practice"


def path_correct(path: str, value, gold: dict) -> bool:
    key = path.split("[")[0]
    if key == "items":
        return any(item_match(value, g) for g in gold.get("items") or [])
    if key == "skills":
        return any(str_match(value, g) for g in gold.get("skills") or [])
    return value_match(value, gold.get(key))


def path_value(data: dict, path: str):
    key, _, idx = path.partition("[")
    return data[key][int(idx[:-1])] if idx else data[key]


def score(data: dict | None, gold: dict) -> dict:
    counts = field_counts(data, gold)
    p, r, f = f1(counts)
    valid = data is not None
    return {"precision": p, "recall": r, "f1": f, "valid": valid, "counts": counts,
            "score": round(100 * (0.8 * f + 0.2 * valid), 1)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=2)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    from extractor.llm import OpenAICompatible

    llm = OpenAICompatible()
    results, conf_pairs = {}, []
    for path in sorted(PRACTICE.glob("*.json")):
        case = json.loads(path.read_text())
        res = extract(case["text"], case["schema"], llm, samples=args.samples)
        r = score(res.data, case["gold"])
        r["attempts"] = res.attempts
        r["first_try"] = res.valid and res.attempts == 1
        r["wrong"] = [k for k, (tp, npred, ngold) in r["counts"].items() if tp < max(npred, ngold)]
        results[case["id"]] = r
        for p, c in res.confidence.items():
            if c is not None:
                conf_pairs.append((c, path_correct(p, path_value(res.data, p), case["gold"])))

    overall = round(sum(r["score"] for r in results.values()) / len(results), 1)
    micro = f1({f"{cid}.{k}": v for cid, r in results.items() for k, v in r["counts"].items()})
    valid_rate = sum(r["valid"] for r in results.values()) / len(results)
    first_rate = sum(r["first_try"] for r in results.values()) / len(results)
    hi = [ok for c, ok in conf_pairs if c >= 0.8]
    lo = [ok for c, ok in conf_pairs if c < 0.8]

    if args.json:
        print(json.dumps({"overall": overall, "model": llm.model, "micro_f1": micro[2], "valid_rate": valid_rate,
                          "cases": {k: {kk: vv for kk, vv in v.items() if kk != "counts"} for k, v in results.items()}},
                         indent=2))
        return
    for cid, r in results.items():
        print(f"{cid:30s} score={r['score']:5.1f}  f1={r['f1']:.2f}  valid={int(r['valid'])}  attempts={r['attempts']}"
              + (f"  missed: {', '.join(r['wrong'])}" if r["wrong"] else ""))
    print(f"\nmodel: {llm.model}")
    print(f"micro field F1: P={micro[0]:.3f} R={micro[1]:.3f} F1={micro[2]:.3f}")
    print(f"schema-valid rate: {valid_rate:.2f}   valid on first try: {first_rate:.2f}")
    if conf_pairs:
        acc = lambda xs: f"{sum(xs) / len(xs):.2f} ({len(xs)} fields)" if xs else "n/a"
        print(f"confidence >= 0.8: accuracy {acc(hi)}   confidence < 0.8: accuracy {acc(lo)}")
    print(f"OVERALL {overall}/100")


if __name__ == "__main__":
    main()
