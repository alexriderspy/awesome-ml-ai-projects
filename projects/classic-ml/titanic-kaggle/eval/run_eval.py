import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from titanic.data import TARGET, kaggle_split, load_titanic
from titanic.models import build_models, cross_validate

SCORED = "gbm"


def evaluate(df, folds: int = 5, seed: int = 0) -> dict:
    train, test_X, test_y = kaggle_split(df)
    X, y = train.drop(columns=[TARGET]), train[TARGET].to_numpy()
    models = build_models(seed)
    cv = cross_validate(models, X, y, folds, seed)
    res = {}
    for name, m in models.items():
        m.fit(X, y)
        res[name] = {"cv_mean": float(cv[name].mean()), "cv_std": float(cv[name].std()),
                     "test_acc": float((m.predict(test_X) == test_y).mean())}
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    res = evaluate(load_titanic(), args.folds)
    overall = round(100 * res[SCORED]["cv_mean"], 1)
    if args.json:
        print(json.dumps({"overall": overall, "models": res}, indent=2))
        return
    for name, r in res.items():
        print(f"{name:12s} cv_acc={r['cv_mean']:.4f} ± {r['cv_std']:.4f}  hidden_test_acc={r['test_acc']:.4f}")
    print(f"\nOVERALL {overall}/100  ({SCORED} CV accuracy)")


if __name__ == "__main__":
    main()
