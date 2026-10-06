import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .features import make_features, supervised


def time_split(X: pd.DataFrame, y: pd.Series, test_days: int = 365):
    return X.iloc[:-test_days], X.iloc[-test_days:], y.iloc[:-test_days], y.iloc[-test_days:]


def persistence(X: pd.DataFrame) -> np.ndarray:
    return X["tmax"].to_numpy()


class DeltaRegressor(BaseEstimator, RegressorMixin):

    def __init__(self, base):
        self.base = base

    def fit(self, X, y):
        self.base_ = clone(self.base).fit(X, np.asarray(y) - X["tmax"].to_numpy())
        return self

    def predict(self, X):
        return self.base_.predict(X) + X["tmax"].to_numpy()


def build_models() -> dict:
    return {
        "ridge": DeltaRegressor(make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 12)))),
        "gbm": DeltaRegressor(HistGradientBoostingRegressor(
            max_iter=200, learning_rate=0.03, max_leaf_nodes=15, min_samples_leaf=50,
            l2_regularization=1.0, random_state=0)),
    }


def mae(y, p) -> float:
    return float(np.mean(np.abs(np.asarray(y) - np.asarray(p))))


def compare(df: pd.DataFrame, test_days: int = 365) -> dict:
    X, y = supervised(df)
    Xtr, Xte, ytr, yte = time_split(X, y, test_days)
    preds = {"persistence": persistence(Xte)}
    models = build_models()
    for name, m in models.items():
        preds[name] = m.fit(Xtr, ytr).predict(Xte)
    return {
        "mae": {k: mae(yte, p) for k, p in preds.items()},
        "test": pd.DataFrame({"actual": yte, **preds}, index=yte.index),
        "models": models,
    }


def forecast_next(df: pd.DataFrame, model) -> tuple[pd.Timestamp, float]:
    last = make_features(df).iloc[[-1]]
    return df.index[-1] + pd.Timedelta(days=1), float(model.predict(last)[0])
