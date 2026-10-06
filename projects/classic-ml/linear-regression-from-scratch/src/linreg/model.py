import numpy as np


def add_bias(X: np.ndarray) -> np.ndarray:
    return np.column_stack([np.ones(len(X)), X])


def mse(y_true, y_pred) -> float:
    return float(np.mean((np.asarray(y_true) - np.asarray(y_pred)) ** 2))


def rmse(y_true, y_pred) -> float:
    return mse(y_true, y_pred) ** 0.5


def r2(y_true, y_pred) -> float:
    y_true = np.asarray(y_true)
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - y_true.mean()) ** 2)
    return float(1 - ss_res / ss_tot)


class ClosedFormLR:

    def fit(self, X, y):
        Xb = add_bias(np.asarray(X, float))
        theta, *_ = np.linalg.lstsq(Xb, y, rcond=None)
        self.intercept_, self.coef_ = float(theta[0]), theta[1:]
        return self

    def predict(self, X):
        return np.asarray(X, float) @ self.coef_ + self.intercept_


class GradientDescentLR:

    def __init__(self, lr: float = 0.1, epochs: int = 500, tol: float = 0.0):
        self.lr, self.epochs, self.tol = lr, epochs, tol

    def fit(self, X, y):
        X, y = np.asarray(X, float), np.asarray(y, float)
        mu, sd = X.mean(0), X.std(0)
        sd[sd == 0] = 1.0
        ym, ys = y.mean(), y.std() or 1.0
        Xs, ys_ = (X - mu) / sd, (y - ym) / ys

        w, b = np.zeros(X.shape[1]), 0.0
        n = len(y)
        self.loss_history_ = []
        for _ in range(self.epochs):
            err = Xs @ w + b - ys_
            with np.errstate(over="ignore", invalid="ignore"):
                loss = float(np.mean(err**2)) * ys**2
            if not np.isfinite(loss):
                raise FloatingPointError("gradient descent diverged; lower the learning rate")
            self.loss_history_.append(loss)
            w -= self.lr * (2 / n) * (Xs.T @ err)
            b -= self.lr * (2 / n) * err.sum()
            if len(self.loss_history_) > 1 and abs(self.loss_history_[-2] - self.loss_history_[-1]) <= self.tol * ys**2:
                break

        self.coef_ = ys * w / sd
        self.intercept_ = float(ym + ys * b - np.sum(self.coef_ * mu))
        return self

    def predict(self, X):
        return np.asarray(X, float) @ self.coef_ + self.intercept_
