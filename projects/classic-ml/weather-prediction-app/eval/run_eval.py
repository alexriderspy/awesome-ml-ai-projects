import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from weather.fetch import CITIES, fetch_daily
from weather.model import compare

START, END = "2015-01-01", "2024-12-31"
EVAL_CITIES = ["London", "New York", "Delhi", "Bengaluru", "Tokyo", "Sydney"]


def score_city(df, model: str) -> dict:
    test_days = int((df.index >= "2024-01-01").sum()) - 1
    m = compare(df, test_days)["mae"]
    m["score"] = round(max(0.0, min(100.0, 100 * (1 - m[model] / m["persistence"]))), 1)
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gbm", choices=["gbm", "ridge"])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    res = {c: score_city(fetch_daily(*CITIES[c], START, END), args.model) for c in EVAL_CITIES}
    overall = round(sum(r["score"] for r in res.values()) / len(res), 1)
    if args.json:
        print(json.dumps({"overall": overall, "model": args.model, "cities": res}, indent=2))
        return
    print(f"MAE in °C on 2024 (scored model: {args.model})")
    for c, r in res.items():
        print(f"{c:10s} score={r['score']:5.1f}  persistence={r['persistence']:.2f}  ridge={r['ridge']:.2f}  gbm={r['gbm']:.2f}")
    print(f"\nOVERALL {overall}/100  (mean % MAE reduction vs persistence)")


if __name__ == "__main__":
    main()
