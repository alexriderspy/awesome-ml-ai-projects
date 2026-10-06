import pandas as pd

from .features import title_of


def eda_report(df: pd.DataFrame) -> str:
    lines = [f"rows: {len(df)}   survival rate: {df['survived'].mean():.3f}", "", "missing values:"]
    miss = df.isna().sum()
    for col, n in miss[miss > 0].items():
        lines.append(f"  {col:10s} {n:5d}  ({n / len(df):.0%})")

    groups = {
        "sex": df["sex"].astype(str),
        "pclass": df["pclass"],
        "title": df["name"].map(title_of),
        "age band": pd.cut(df["age"], [0, 14, 30, 50, 100], labels=["0-13", "14-29", "30-49", "50+"]).astype(str),
        "family size": (df["sibsp"] + df["parch"] + 1).clip(upper=5).map(lambda n: "5+" if n == 5 else str(n)),
    }
    for name, key in groups.items():
        lines += ["", f"survival by {name}:"]
        tab = df.groupby(key, observed=True)["survived"].agg(["mean", "count"])
        for k, row in tab.iterrows():
            lines.append(f"  {str(k):8s} {row['mean']:.3f}  (n={int(row['count'])})")
    return "\n".join(lines)
