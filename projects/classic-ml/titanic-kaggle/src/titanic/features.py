import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

TITLE_MAP = {
    "Mr": "Mr", "Mrs": "Mrs", "Miss": "Miss", "Master": "Master",
    "Mlle": "Miss", "Ms": "Miss", "Mme": "Mrs", "Lady": "Rare", "Countess": "Rare",
    "Dona": "Rare", "Don": "Rare", "Sir": "Rare", "Jonkheer": "Rare",
    "Capt": "Officer", "Col": "Officer", "Major": "Officer", "Dr": "Officer", "Rev": "Officer",
}

NUMERIC = ["pclass", "age", "fare_per_person", "family_size", "is_alone", "has_cabin", "is_child"]
CATEGORICAL = ["sex", "title", "embarked", "deck"]


def title_of(name: str) -> str:
    try:
        raw = name.split(",", 1)[1].split(".", 1)[0].strip()
    except IndexError:
        return "Rare"
    return TITLE_MAP.get(raw, "Rare")


class TitanicFeatures(BaseEstimator, TransformerMixin):

    def fit(self, X: pd.DataFrame, y=None):
        df = self._base(X)
        self.age_by_title_ = df.groupby("title")["age"].median().to_dict()
        self.age_median_ = float(df["age"].median())
        self.fare_median_ = float(df["fare"].median())
        self.ticket_counts_ = X["ticket"].astype(str).value_counts().to_dict()
        return self

    def _base(self, X: pd.DataFrame) -> pd.DataFrame:
        df = pd.DataFrame(index=X.index)
        df["pclass"] = X["pclass"].astype(int)
        df["sex"] = X["sex"].astype(str)
        df["title"] = X["name"].astype(str).map(title_of)
        df["age"] = pd.to_numeric(X["age"], errors="coerce")
        df["fare"] = pd.to_numeric(X["fare"], errors="coerce")
        df["family_size"] = X["sibsp"].astype(int) + X["parch"].astype(int) + 1
        df["is_alone"] = (df["family_size"] == 1).astype(int)
        cabin = X["cabin"].astype("string")
        df["has_cabin"] = cabin.notna().astype(int)
        df["deck"] = cabin.str[0].fillna("U").replace({"T": "U"}).astype(str)
        df["embarked"] = X["embarked"].astype("string").fillna("S").astype(str)
        return df

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        df = self._base(X)
        fill = df["title"].map(self.age_by_title_).fillna(self.age_median_)
        df["age"] = df["age"].fillna(fill)
        df["fare"] = df["fare"].fillna(self.fare_median_)
        ticket = X["ticket"].astype(str)
        seen = ticket.map(self.ticket_counts_).fillna(0)
        batch = ticket.map(ticket.value_counts())
        df["fare_per_person"] = np.log1p(df["fare"] / np.maximum(seen, batch).clip(lower=1))
        df["is_child"] = (df["age"] < 14).astype(int)
        return df[NUMERIC + CATEGORICAL]
