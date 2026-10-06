import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from house_price.metrics import coverage, mae, report, rmse
from house_price.model import FEATURES, TARGET, HousePriceModel, add_features, load_model, split, train_and_save


def fake_housing(n=600, seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "MedInc": rng.uniform(1, 10, n), "HouseAge": rng.integers(1, 52, n).astype(float),
        "AveRooms": rng.uniform(3, 8, n), "AveBedrms": rng.uniform(0.8, 1.4, n),
        "Population": rng.uniform(200, 3000, n), "AveOccup": rng.uniform(1.5, 4, n),
        "Latitude": rng.uniform(32.5, 42, n), "Longitude": rng.uniform(-124, -114, n),
    })
    coast = (df["Longitude"] < -121).astype(float)
    df[TARGET] = (0.4 * df["MedInc"] + 1.0 * coast + rng.normal(0, 0.3, n)).clip(0.15, 5.0)
    return df


def test_add_features_shape():
    X = add_features(fake_housing(10)[FEATURES])
    assert len(X.columns) == len(FEATURES) + 4 and not X.isna().any().any()


def test_interval_contains_point_and_is_roughly_calibrated():
    df = fake_housing(1500)
    Xtr, Xte, ytr, yte = split(df)
    m = HousePriceModel().fit(Xtr, ytr)
    lo, p, hi = m.predict_interval(Xte)
    assert (lo <= p).all() and (p <= hi).all()
    assert m.margin_ != 0.0
    assert 0.65 <= coverage(yte, lo, hi) <= 0.95
    assert rmse(yte, p) < rmse(yte, np.full_like(yte, ytr.mean()))


def test_artifact_roundtrip(tmp_path):
    path = tmp_path / "m.joblib"
    res = train_and_save(fake_housing(400), path)
    loaded = load_model(path)
    Xte, _ = res["test"]
    np.testing.assert_allclose(loaded.predict(Xte), res["model"].predict(Xte))


def test_metrics_and_score():
    y = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    assert rmse(y, y) == 0 and mae(y, y + 1) == 1
    assert coverage(y, y - 1, y + 1) == 1.0
    perfect = report(y, y - 0.1, y, y + 0.1, y.mean())
    assert perfect["rmse_skill"] == 1.0 and perfect["calibration"] == pytest.approx(0.75)
    lazy = report(y, y * 0, np.full_like(y, y.mean()), y * 0 + 10, y.mean())
    assert lazy["score"] < perfect["score"]
