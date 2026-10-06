from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
ARTIFACT = ROOT / "artifacts" / "house_price.joblib"
FEATURES = ["MedInc", "HouseAge", "AveRooms", "AveBedrms", "Population", "AveOccup", "Latitude", "Longitude"]
TARGET = "MedHouseVal"
LOW_Q, HIGH_Q = 0.1, 0.9


def load_data(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    from sklearn.datasets import fetch_california_housing

    return fetch_california_housing(as_frame=True, data_home=str(data_dir)).frame


def split(df: pd.DataFrame, seed: int = 42):
    train, test = train_test_split(df, test_size=0.2, random_state=seed)
    return train[FEATURES], test[FEATURES], train[TARGET].to_numpy(), test[TARGET].to_numpy()


def add_features(X: pd.DataFrame) -> pd.DataFrame:
    X = X[FEATURES].copy()
    X["BedroomShare"] = X["AveBedrms"] / X["AveRooms"].clip(lower=1e-3)
    X["RoomsPerPerson"] = X["AveRooms"] / X["AveOccup"].clip(lower=1e-3)
    X["RotA"] = X["Latitude"] + X["Longitude"]
    X["RotB"] = X["Latitude"] - X["Longitude"]
    return X


def _pipe(**kw):
    return make_pipeline(
        FunctionTransformer(add_features),
        HistGradientBoostingRegressor(max_iter=500, learning_rate=0.08, max_leaf_nodes=48,
                                      min_samples_leaf=20, l2_regularization=1.0, random_state=0, **kw),
    )


class HousePriceModel:

    def fit(self, X: pd.DataFrame, y, calibrate: bool = True, seed: int = 0):
        y = np.asarray(y, float)
        self.point = _pipe().fit(X, y)
        if calibrate:
            Xq, Xc, yq, yc = train_test_split(X, y, test_size=0.2, random_state=seed)
        else:
            Xq, yq = X, y
        self.low = _pipe(loss="quantile", quantile=LOW_Q).fit(Xq, yq)
        self.high = _pipe(loss="quantile", quantile=HIGH_Q).fit(Xq, yq)
        self.margin_ = 0.0
        if calibrate:
            scores = np.maximum(self.low.predict(Xc) - yc, yc - self.high.predict(Xc))
            n, alpha = len(yc), 1 - (HIGH_Q - LOW_Q)
            self.margin_ = float(np.quantile(scores, min(1.0, (1 - alpha) * (n + 1) / n)))
        self.train_stats_ = X[FEATURES].describe().T[["min", "50%", "max"]]
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self.point.predict(X)

    def predict_interval(self, X: pd.DataFrame):
        p = self.point.predict(X)
        lo, hi = self.low.predict(X) - self.margin_, self.high.predict(X) + self.margin_
        return np.minimum(lo, p), p, np.maximum(hi, p)


def train_and_save(df: pd.DataFrame | None = None, path: Path = ARTIFACT) -> dict:
    df = load_data() if df is None else df
    Xtr, Xte, ytr, yte = split(df)
    model = HousePriceModel().fit(Xtr, ytr)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    return {"model": model, "test": (Xte, yte), "train_mean": float(ytr.mean())}


def load_model(path: Path = ARTIFACT) -> HousePriceModel:
    return joblib.load(path)
