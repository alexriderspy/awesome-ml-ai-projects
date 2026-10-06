import argparse
from pathlib import Path

from .data import TARGET, kaggle_split, load_titanic
from .eda import eda_report
from .models import build_models, cross_validate
from .submission import check_submission, write_submission


def main() -> None:
    ap = argparse.ArgumentParser(description="Titanic survival, Kaggle style")
    ap.add_argument("--out", default="outputs", help="where to write submission.csv and plots")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    out = Path(args.out)

    df = load_titanic()
    train, test_X, test_y = kaggle_split(df)
    print(f"train {len(train)} rows, hidden test {len(test_X)} rows\n")
    print("== EDA (train only) ==")
    print(eda_report(train))

    X, y = train.drop(columns=[TARGET]), train[TARGET].to_numpy()
    models = build_models(args.seed)
    print(f"\n== {args.folds}-fold CV accuracy ==")
    for name, scores in cross_validate(models, X, y, args.folds, args.seed).items():
        print(f"  {name:12s} {scores.mean():.4f} ± {scores.std():.4f}")

    best = models["gbm"].fit(X, y)
    sub = write_submission(best, test_X, out / "submission.csv")
    check_submission(sub, test_X)
    print(f"\nwrote {out / 'submission.csv'} ({len(sub)} rows)")
    print(f"hidden-test accuracy (gbm): {(sub['Survived'].to_numpy() == test_y).mean():.4f}")

    from .importance import feature_importance, plot_importance

    imp = feature_importance(best, test_X, test_y, seed=args.seed)
    plot_importance(imp).savefig(out / "feature_importance.png", dpi=150)
    print("\npermutation importance on hidden test (accuracy drop):")
    for _, r in imp.iloc[::-1].iterrows():
        print(f"  {r['feature']:9s} {r['importance']:.4f}")
    print(f"saved {out / 'feature_importance.png'}")


if __name__ == "__main__":
    main()
