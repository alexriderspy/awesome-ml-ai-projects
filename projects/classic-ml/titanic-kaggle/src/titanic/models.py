import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .features import CATEGORICAL, NUMERIC, TitanicFeatures


class GenderRule(BaseEstimator, ClassifierMixin):

    def fit(self, X, y=None):
        self.classes_ = np.array([0, 1])
        return self

    def predict(self, X):
        return (X["sex"].astype(str) == "female").astype(int).to_numpy()


def _encoder(scale: bool) -> ColumnTransformer:
    num = StandardScaler() if scale else "passthrough"
    return ColumnTransformer([
        ("num", num, NUMERIC),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
    ])


def build_models(seed: int = 0) -> dict:
    return {
        "majority": DummyClassifier(strategy="most_frequent"),
        "gender_rule": GenderRule(),
        "logistic": make_pipeline(TitanicFeatures(), _encoder(scale=True), LogisticRegression(max_iter=1000)),
        "gbm": make_pipeline(
            TitanicFeatures(), _encoder(scale=False),
            HistGradientBoostingClassifier(learning_rate=0.05, max_iter=200, max_depth=4,
                                           l2_regularization=1.0, random_state=seed),
        ),
    }


def cross_validate(models: dict, X: pd.DataFrame, y, folds: int = 5, seed: int = 0) -> dict:
    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    return {name: cross_val_score(m, X, y, cv=cv, scoring="accuracy") for name, m in models.items()}
