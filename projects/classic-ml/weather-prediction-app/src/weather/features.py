import numpy as np
import pandas as pd

BASE = ["tmax", "tmin", "tmean", "precip", "wind", "radiation", "pressure", "humidity"]


def make_features(df: pd.DataFrame) -> pd.DataFrame:
    f = df[BASE].copy()
    for lag in (1, 2, 3, 7):
        f[f"tmax_lag{lag}"] = df["tmax"].shift(lag)
    for w in (3, 7, 30):
        f[f"tmax_roll{w}"] = df["tmax"].rolling(w).mean()
    f["tmin_roll7"] = df["tmin"].rolling(7).mean()
    f["tmax_diff1"] = df["tmax"] - df["tmax"].shift(1)
    f["pressure_diff1"] = df["pressure"] - df["pressure"].shift(1)
    f["range"] = df["tmax"] - df["tmin"]
    doy = (df.index + pd.Timedelta(days=1)).dayofyear.to_numpy()
    f["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    f["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    return f


def make_target(df: pd.DataFrame) -> pd.Series:
    return df["tmax"].shift(-1).rename("tmax_tomorrow")


def supervised(df: pd.DataFrame):
    X, y = make_features(df), make_target(df)
    ok = X.notna().all(axis=1) & y.notna()
    return X[ok], y[ok]
