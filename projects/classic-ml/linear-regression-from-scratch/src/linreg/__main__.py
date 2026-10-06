import argparse
from pathlib import Path

from .data import make_salary_data, train_test_split
from .model import ClosedFormLR, GradientDescentLR, mse, r2, rmse


def run(n=200, noise=6000.0, seed=0, lr=0.1, epochs=500, multi=False):
    X, y = make_salary_data(n, noise, seed, multi)
    Xtr, Xte, ytr, yte = train_test_split(X, y, seed=seed)
    models = {
        "closed form": ClosedFormLR().fit(Xtr, ytr),
        "gradient descent": GradientDescentLR(lr=lr, epochs=epochs).fit(Xtr, ytr),
    }
    try:
        from sklearn.linear_model import LinearRegression

        models["scikit-learn"] = LinearRegression().fit(Xtr, ytr)
    except ImportError:
        pass
    rows = []
    for name, m in models.items():
        p = m.predict(Xte)
        rows.append({"model": name, "intercept": float(m.intercept_), "coef": [float(c) for c in m.coef_],
                     "test_r2": r2(yte, p), "test_rmse": rmse(yte, p)})
    return {"data": (Xtr, Xte, ytr, yte), "models": models, "rows": rows,
            "closed_form_train_mse": mse(ytr, models["closed form"].predict(Xtr))}


def main() -> None:
    ap = argparse.ArgumentParser(description="Linear regression from scratch on synthetic salary data")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--noise", type=float, default=6000.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--lr", type=float, default=0.1)
    ap.add_argument("--epochs", type=int, default=500)
    ap.add_argument("--multi", action="store_true", help="add a second feature (certifications)")
    ap.add_argument("--plots", help="folder to save loss_curve.png and fit_line.png")
    args = ap.parse_args()

    res = run(args.n, args.noise, args.seed, args.lr, args.epochs, args.multi)
    print(f"{'model':18s} {'intercept':>11s}  {'coef':24s} {'test R2':>8s} {'test RMSE':>10s}")
    for r in res["rows"]:
        coef = ", ".join(f"{c:,.1f}" for c in r["coef"])
        print(f"{r['model']:18s} {r['intercept']:11,.1f}  {coef:24s} {r['test_r2']:8.4f} {r['test_rmse']:10,.1f}")

    if args.plots:
        from .plots import fit_line, loss_curve

        out = Path(args.plots)
        out.mkdir(parents=True, exist_ok=True)
        gd = res["models"]["gradient descent"]
        loss_curve(gd.loss_history_, res["closed_form_train_mse"]).savefig(out / "loss_curve.png", dpi=150)
        fit_line(*res["data"], res["models"]).savefig(out / "fit_line.png", dpi=150)
        print(f"saved plots to {out}/")


if __name__ == "__main__":
    main()
