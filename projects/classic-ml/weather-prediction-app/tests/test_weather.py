import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from weather.features import make_features, make_target, supervised
from weather.fetch import fetch_daily, parse_response
from weather.model import DeltaRegressor, compare, forecast_next, persistence, time_split

FIXTURE = ROOT / "tests" / "fixtures" / "london_2023-09_2024-03.csv"


@pytest.fixture
def df():
    return pd.read_csv(FIXTURE, index_col="date", parse_dates=["date"])


def test_parse_response():
    payload = {"daily": {"time": ["2024-01-01", "2024-01-02"], "temperature_2m_max": [7.4, 7.0],
                         "temperature_2m_min": [3.4, 2.5]}}
    out = parse_response(payload)
    assert list(out.columns) == ["tmax", "tmin"]
    assert out.index[0] == pd.Timestamp("2024-01-01")


def test_fetch_uses_cache_without_network(df, tmp_path, monkeypatch):
    df.to_csv(tmp_path / "51.51_-0.13_2023-09-01_2024-03-31.csv")
    monkeypatch.setitem(sys.modules, "requests", None)
    out = fetch_daily(51.51, -0.13, "2023-09-01", "2024-03-31", tmp_path)
    assert len(out) == len(df)


def test_target_is_tomorrow_and_features_dont_peek(df):
    y = make_target(df)
    assert y.iloc[0] == df["tmax"].iloc[1]
    X1 = make_features(df)
    df2 = df.copy()
    df2.iloc[100:] += 50
    X2 = make_features(df2)
    pd.testing.assert_frame_equal(X1.iloc[:100], X2.iloc[:100])


def test_supervised_has_no_gaps(df):
    X, y = supervised(df)
    assert not X.isna().any().any() and not y.isna().any()
    assert len(X) == len(df) - 30


def test_time_split_keeps_order(df):
    X, y = supervised(df)
    Xtr, Xte, _, _ = time_split(X, y, test_days=30)
    assert Xtr.index.max() < Xte.index.min() and len(Xte) == 30


def test_persistence_and_delta():
    X = pd.DataFrame({"tmax": [10.0, 12.0, 14.0], "other": [0.0, 1.0, 2.0]})
    assert list(persistence(X)) == [10.0, 12.0, 14.0]
    from sklearn.linear_model import LinearRegression

    m = DeltaRegressor(LinearRegression()).fit(X, X["tmax"] + 1)
    np.testing.assert_allclose(m.predict(X), X["tmax"] + 1)


def test_compare_and_forecast(df):
    res = compare(df, test_days=40)
    assert set(res["mae"]) == {"persistence", "ridge", "gbm"}
    assert all(0 < v < 10 for v in res["mae"].values())
    day, t = forecast_next(df, res["models"]["gbm"])
    assert day == df.index[-1] + pd.Timedelta(days=1)
    assert -20 < t < 40


def test_eval_scoring(df, monkeypatch):
    import run_eval

    shifted = df.copy()
    shifted.index = pd.date_range(end="2024-02-29", periods=len(df), freq="D")
    r = run_eval.score_city(shifted, "gbm")
    assert 0 <= r["score"] <= 100
    json.dumps(r)
