import argparse

import pandas as pd

from .metrics import report
from .model import ARTIFACT, FEATURES, load_model, train_and_save


def main() -> None:
    ap = argparse.ArgumentParser(description="California house price predictor")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("train")
    pr = sub.add_parser("predict")
    for f in FEATURES:
        pr.add_argument(f"--{f}", type=float)
    args = ap.parse_args()

    if args.cmd == "train":
        res = train_and_save()
        Xte, yte = res["test"]
        m = res["model"]
        lo, p, hi = m.predict_interval(Xte)
        r = report(yte, lo, p, hi, res["train_mean"])
        print(f"saved {ARTIFACT}")
        print(f"test RMSE {r['rmse']:.4f}  MAE {r['mae']:.4f}  (x $100k)")
        print(f"80% band coverage {r['coverage']:.3f}, mean width {r['band_width']:.3f}")
        return

    model = load_model()
    row = {f: getattr(args, f) if getattr(args, f) is not None else model.train_stats_.loc[f, "50%"] for f in FEATURES}
    lo, p, hi = model.predict_interval(pd.DataFrame([row]))
    print(f"predicted median value: ${p[0] * 1e5:,.0f}  (80% band ${lo[0] * 1e5:,.0f} - ${hi[0] * 1e5:,.0f})")


if __name__ == "__main__":
    main()
