import numpy as np

from .model import HIGH_Q, LOW_Q


def rmse(y, p) -> float:
    return float(np.sqrt(np.mean((np.asarray(y) - np.asarray(p)) ** 2)))


def mae(y, p) -> float:
    return float(np.mean(np.abs(np.asarray(y) - np.asarray(p))))


def coverage(y, lo, hi) -> float:
    y = np.asarray(y)
    return float(np.mean((y >= lo) & (y <= hi)))


def report(y_test, lo, p, hi, y_train_mean: float) -> dict:
    base = np.full_like(np.asarray(y_test, float), y_train_mean)
    r = {
        "rmse": rmse(y_test, p), "mae": mae(y_test, p),
        "rmse_baseline": rmse(y_test, base), "mae_baseline": mae(y_test, base),
        "coverage": coverage(y_test, lo, hi), "band_width": float(np.mean(hi - lo)),
    }
    target = HIGH_Q - LOW_Q
    r["rmse_skill"] = max(0.0, 1 - r["rmse"] / r["rmse_baseline"])
    r["mae_skill"] = max(0.0, 1 - r["mae"] / r["mae_baseline"])
    r["calibration"] = max(0.0, 1 - abs(r["coverage"] - target) / target)
    r["score"] = round(100 * (0.5 * r["rmse_skill"] + 0.25 * r["mae_skill"] + 0.25 * r["calibration"]), 1)
    return r
