import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from linreg.data import make_salary_data, train_test_split
from linreg.model import ClosedFormLR, GradientDescentLR, r2, rmse

PRACTICE = Path(__file__).parent / "practice" / "cases.json"


def rel_err(model, ref) -> float:
    a = np.r_[model.intercept_, model.coef_]
    b = np.r_[ref.intercept_, ref.coef_]
    return float(np.max(np.abs(a - b) / np.maximum(np.abs(b), 1e-9)))


def agreement(err: float, ok: float, zero: float) -> float:
    if err <= ok:
        return 1.0
    return max(0.0, 1 - (err - ok) / (zero - ok))


def score_case(case: dict, lr: float, epochs: int) -> dict:
    from sklearn.linear_model import LinearRegression

    X, y = make_salary_data(case["n"], case["noise"], case["seed"], case["multi"])
    Xtr, Xte, ytr, yte = train_test_split(X, y, seed=case["seed"])
    cf = ClosedFormLR().fit(Xtr, ytr)
    gd = GradientDescentLR(lr=lr, epochs=epochs).fit(Xtr, ytr)
    sk = LinearRegression().fit(Xtr, ytr)

    p_gd, p_sk = gd.predict(Xte), sk.predict(Xte)
    r = {
        "cf_err": rel_err(cf, sk),
        "gd_err": rel_err(gd, sk),
        "r2": r2(yte, p_gd),
        "r2_sklearn": r2(yte, p_sk),
        "rmse": rmse(yte, p_gd),
    }
    parts = {
        "closed_form": agreement(r["cf_err"], 1e-6, 1e-2),
        "gd": agreement(r["gd_err"], 1e-3, 5e-2),
        "heldout": max(0.0, min(1.0, r["r2"] / r["r2_sklearn"])) if r["r2_sklearn"] > 0 else 0.0,
        "noise_floor": 1.0 if r["rmse"] <= 1.2 * case["noise"] else 0.0,
    }
    r.update(parts)
    r["score"] = round(100 * (0.3 * parts["closed_form"] + 0.3 * parts["gd"] + 0.25 * parts["heldout"] + 0.15 * parts["noise_floor"]), 1)
    return r


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lr", type=float, default=0.1)
    ap.add_argument("--epochs", type=int, default=500)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    cases = json.loads(PRACTICE.read_text())
    results = {c["id"]: score_case(c, args.lr, args.epochs) for c in cases}
    overall = round(sum(r["score"] for r in results.values()) / len(results), 1)
    if args.json:
        print(json.dumps({"overall": overall, "cases": results}, indent=2))
        return
    for cid, r in results.items():
        print(f"{cid:13s} score={r['score']:5.1f}  R2={r['r2']:.4f} (sklearn {r['r2_sklearn']:.4f})  "
              f"RMSE={r['rmse']:9,.0f}  cf_err={r['cf_err']:.1e}  gd_err={r['gd_err']:.1e}")
    print(f"\nOVERALL {overall}/100")


if __name__ == "__main__":
    main()
