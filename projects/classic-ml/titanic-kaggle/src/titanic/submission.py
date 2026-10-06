from pathlib import Path

import numpy as np
import pandas as pd


def write_submission(model, test_features: pd.DataFrame, path) -> pd.DataFrame:
    sub = pd.DataFrame({
        "PassengerId": test_features["PassengerId"].astype(int),
        "Survived": np.asarray(model.predict(test_features)).astype(int),
    })
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    sub.to_csv(path, index=False)
    return sub


def check_submission(sub: pd.DataFrame, test_features: pd.DataFrame) -> None:
    if list(sub.columns) != ["PassengerId", "Survived"]:
        raise ValueError(f"columns must be PassengerId,Survived, got {list(sub.columns)}")
    if len(sub) != len(test_features) or set(sub["PassengerId"]) != set(test_features["PassengerId"]):
        raise ValueError("submission ids don't match the test set")
    if not set(sub["Survived"].unique()) <= {0, 1}:
        raise ValueError("Survived must be 0 or 1")
