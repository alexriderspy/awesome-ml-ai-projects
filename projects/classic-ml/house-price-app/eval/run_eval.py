import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from house_price.metrics import mae, report, rmse
from house_price.model import HousePriceModel, load_data, split


def evaluate(df) -> dict:
    from sklearn.linear_model import LinearRegression

    Xtr, Xte, ytr, yte = split(df)
    model = HousePriceModel().fit(Xtr, ytr)
    lo, p, hi = model.predict_interval(Xte)
    r = report(yte, lo, p, hi, float(ytr.mean()))
    lin = LinearRegression().fit(Xtr, ytr).predict(Xte)
    r["linear_rmse"], r["linear_mae"] = rmse(yte, lin), mae(yte, lin)
    r["n_test"] = len(yte)
    return r


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    r = evaluate(load_data())
    if args.json:
        print(json.dumps(r, indent=2))
        return
    print(f"test rows: {r['n_test']}   (prices in $100k)")
    print(f"{'model':22s} {'RMSE':>7s} {'MAE':>7s}")
    print(f"{'predict train mean':22s} {r['rmse_baseline']:7.4f} {r['mae_baseline']:7.4f}")
    print(f"{'linear regression':22s} {r['linear_rmse']:7.4f} {r['linear_mae']:7.4f}")
    print(f"{'gradient boosting':22s} {r['rmse']:7.4f} {r['mae']:7.4f}")
    print(f"\n80% band: coverage {r['coverage']:.3f}, mean width {r['band_width']:.3f}")
    print(f"rmse_skill={r['rmse_skill']:.3f}  mae_skill={r['mae_skill']:.3f}  calibration={r['calibration']:.3f}")
    print(f"\nOVERALL {r['score']}/100")


if __name__ == "__main__":
    main()
