from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
LEAKY = ["boat", "body", "home.dest"]
TARGET = "survived"


def load_titanic(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    cache = Path(data_dir) / "titanic.csv"
    if cache.exists():
        df = pd.read_csv(cache)
    else:
        from sklearn.datasets import fetch_openml

        df = fetch_openml("titanic", version=1, as_frame=True, data_home=str(data_dir)).frame
        df = df.drop(columns=LEAKY)
        df[TARGET] = df[TARGET].astype(int)
        df.insert(0, "PassengerId", range(1, len(df) + 1))
        cache.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(cache, index=False)
    return df.drop(columns=[c for c in LEAKY if c in df.columns])


def kaggle_split(df: pd.DataFrame, test_frac: float = 0.3, seed: int = 42):
    from sklearn.model_selection import train_test_split

    train, test = train_test_split(df, test_size=test_frac, random_state=seed, stratify=df[TARGET])
    return train.reset_index(drop=True), test.drop(columns=[TARGET]).reset_index(drop=True), test[TARGET].to_numpy()
