import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from titanic.data import TARGET, kaggle_split, load_titanic
from titanic.eda import eda_report
from titanic.features import CATEGORICAL, NUMERIC, TitanicFeatures, title_of
from titanic.importance import feature_importance
from titanic.models import GenderRule, build_models, cross_validate
from titanic.submission import check_submission, write_submission

FIXTURE = ROOT / "tests" / "fixtures"


@pytest.fixture
def df(tmp_path):
    (tmp_path / "titanic.csv").write_text((FIXTURE / "titanic_tiny.csv").read_text())
    return load_titanic(tmp_path)


@pytest.mark.parametrize("name,title", [
    ("Allen, Miss. Elisabeth Walton", "Miss"),
    ("Smith, Mr. John", "Mr"),
    ("Brown, Mme. Anna", "Mrs"),
    ("Doe, Rev. Peter", "Officer"),
    ("Rothes, the Countess. of (Lucy)", "Rare"),
    ("nocomma", "Rare"),
])
def test_title_of(name, title):
    assert title_of(name) == title


def test_split_hides_labels(df):
    train, test_X, test_y = kaggle_split(df)
    assert TARGET not in test_X.columns
    assert len(train) + len(test_X) == len(df) == len(train) + len(test_y)
    assert not set(train["PassengerId"]) & set(test_X["PassengerId"])


def test_features_fill_missing_and_learn_from_train_only(df):
    fe = TitanicFeatures().fit(df.iloc[:40])
    out = fe.transform(df.iloc[40:])
    assert list(out.columns) == NUMERIC + CATEGORICAL
    assert not out[NUMERIC].isna().any().any()
    assert len(fe.transform(df.iloc[[0]])) == 1


def test_gender_rule():
    X = pd.DataFrame({"sex": ["female", "male"]})
    assert list(GenderRule().fit(X).predict(X)) == [1, 0]


def test_cv_runs_for_every_model(df):
    X, y = df.drop(columns=[TARGET]), df[TARGET].to_numpy()
    scores = cross_validate(build_models(), X, y, folds=3)
    assert set(scores) == {"majority", "gender_rule", "logistic", "gbm"}
    assert all(len(s) == 3 and ((0 <= s) & (s <= 1)).all() for s in scores.values())
    assert scores["majority"].mean() <= 0.55


def test_submission_roundtrip(df, tmp_path):
    train, test_X, _ = kaggle_split(df)
    model = build_models()["gbm"].fit(train.drop(columns=[TARGET]), train[TARGET])
    sub = write_submission(model, test_X, tmp_path / "sub.csv")
    check_submission(pd.read_csv(tmp_path / "sub.csv"), test_X)
    bad = sub.assign(Survived=2)
    with pytest.raises(ValueError):
        check_submission(bad, test_X)
    with pytest.raises(ValueError):
        check_submission(sub.iloc[:-1], test_X)


def test_importance_and_eda(df):
    X, y = df.drop(columns=[TARGET]), df[TARGET].to_numpy()
    model = build_models()["logistic"].fit(X, y)
    imp = feature_importance(model, X, y, repeats=2)
    assert "sex" in set(imp["feature"]) and "PassengerId" not in set(imp["feature"])
    assert np.isfinite(imp["importance"]).all()
    report = eda_report(df)
    assert "survival by sex" in report and "missing values" in report
