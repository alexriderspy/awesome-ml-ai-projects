import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from linreg.data import PER_YEAR, make_salary_data, train_test_split
from linreg.model import ClosedFormLR, GradientDescentLR, r2, rmse
from run_eval import agreement, score_case


def test_data_is_seeded_and_shaped():
    X1, y1 = make_salary_data(50, seed=7)
    X2, y2 = make_salary_data(50, seed=7)
    assert X1.shape == (50, 1) and np.array_equal(y1, y2)
    assert make_salary_data(50, multi=True)[0].shape == (50, 2)


def test_split_is_disjoint_and_complete():
    X, y = make_salary_data(100)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_frac=0.2)
    assert len(yte) == 20 and len(ytr) == 80
    assert sorted(np.r_[ytr, yte]) == sorted(y)


def test_closed_form_recovers_exact_line():
    X = np.arange(10, dtype=float)[:, None]
    y = 3.0 + 2.0 * X[:, 0]
    m = ClosedFormLR().fit(X, y)
    assert m.intercept_ == pytest.approx(3.0)
    assert m.coef_[0] == pytest.approx(2.0)


@pytest.mark.parametrize("multi", [False, True])
def test_gd_matches_closed_form(multi):
    X, y = make_salary_data(300, seed=3, multi=multi)
    cf = ClosedFormLR().fit(X, y)
    gd = GradientDescentLR(lr=0.1, epochs=1000).fit(X, y)
    np.testing.assert_allclose(gd.coef_, cf.coef_, rtol=1e-4)
    assert gd.intercept_ == pytest.approx(cf.intercept_, rel=1e-4)


def test_gd_loss_goes_down():
    X, y = make_salary_data(100)
    gd = GradientDescentLR(lr=0.1, epochs=100).fit(X, y)
    h = gd.loss_history_
    assert h[-1] < h[0] and all(b <= a + 1e-9 for a, b in zip(h, h[1:]))


def test_gd_diverges_loudly_with_huge_lr():
    X, y = make_salary_data(100)
    with pytest.raises(FloatingPointError):
        GradientDescentLR(lr=5.0, epochs=2000).fit(X, y)


def test_slope_close_to_truth():
    X, y = make_salary_data(2000, noise=3000, seed=1)
    assert ClosedFormLR().fit(X, y).coef_[0] == pytest.approx(PER_YEAR, rel=0.02)


def test_metrics():
    y = np.array([1.0, 2.0, 3.0])
    assert r2(y, y) == 1.0
    assert rmse(y, y + 2) == pytest.approx(2.0)


def test_scorer():
    assert agreement(0.0, 1e-3, 5e-2) == 1.0
    assert agreement(1.0, 1e-3, 5e-2) == 0.0
    good = score_case({"n": 200, "noise": 6000, "seed": 0, "multi": False}, lr=0.1, epochs=500)
    bad = score_case({"n": 200, "noise": 6000, "seed": 0, "multi": False}, lr=0.1, epochs=3)
    assert good["score"] == 100.0
    assert bad["score"] < good["score"]
