import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.inspection import permutation_importance

RAW = ["pclass", "name", "sex", "age", "sibsp", "parch", "ticket", "fare", "cabin", "embarked"]


def feature_importance(model, X: pd.DataFrame, y, seed: int = 0, repeats: int = 20) -> pd.DataFrame:
    r = permutation_importance(model, X, y, scoring="accuracy", n_repeats=repeats, random_state=seed,
                               n_jobs=1, max_samples=1.0)
    names = list(X.columns)
    df = pd.DataFrame({"feature": names, "importance": r.importances_mean, "std": r.importances_std})
    return df[df["feature"].isin(RAW)].sort_values("importance").reset_index(drop=True)


def plot_importance(imp: pd.DataFrame, title: str = "Permutation importance (held-out accuracy drop)"):
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.barh(imp["feature"], imp["importance"], xerr=imp["std"], color="#111111", ecolor="#999999")
    ax.set_xlabel("accuracy drop when shuffled")
    ax.set_title(title, fontsize=10)
    fig.tight_layout()
    return fig
