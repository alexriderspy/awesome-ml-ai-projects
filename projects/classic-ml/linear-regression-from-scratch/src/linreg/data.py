import numpy as np

BASE_SALARY = 35_000.0
PER_YEAR = 9_000.0
PER_CERT = 4_000.0


def make_salary_data(n: int = 200, noise: float = 6_000.0, seed: int = 0, multi: bool = False):
    rng = np.random.default_rng(seed)
    years = rng.uniform(0, 15, n).round(1)
    y = BASE_SALARY + PER_YEAR * years + rng.normal(0, noise, n)
    cols = [years]
    if multi:
        certs = rng.integers(0, 6, n).astype(float)
        y = y + PER_CERT * certs
        cols.append(certs)
    return np.column_stack(cols), y


def train_test_split(X, y, test_frac: float = 0.2, seed: int = 0):
    idx = np.random.default_rng(seed).permutation(len(y))
    n_test = max(1, int(round(len(y) * test_frac)))
    test, train = idx[:n_test], idx[n_test:]
    return X[train], X[test], y[train], y[test]
