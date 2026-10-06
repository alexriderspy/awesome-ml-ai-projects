import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def loss_curve(loss_history, closed_form_mse=None):
    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.plot(np.arange(1, len(loss_history) + 1), loss_history, color="#111111", label="gradient descent")
    if closed_form_mse is not None:
        ax.axhline(closed_form_mse, color="#c0392b", ls="--", lw=1, label="closed-form MSE")
    ax.set_yscale("log")
    ax.set_xlabel("epoch")
    ax.set_ylabel("train MSE (log)")
    ax.set_title("Gradient descent loss")
    ax.legend(frameon=False)
    fig.tight_layout()
    return fig


def fit_line(X_train, X_test, y_train, y_test, models: dict):
    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.scatter(X_train[:, 0], y_train, s=12, color="#999999", label="train")
    ax.scatter(X_test[:, 0], y_test, s=16, color="#111111", marker="x", label="test")
    grid = np.linspace(X_train[:, 0].min(), X_train[:, 0].max(), 50)
    styles = ["-", "--", ":"]
    for (label, m), ls in zip(models.items(), styles):
        Xg = np.column_stack([grid] + [np.full_like(grid, X_train[:, j].mean()) for j in range(1, X_train.shape[1])])
        ax.plot(grid, m.predict(Xg), ls=ls, lw=2, label=label)
    ax.set_xlabel("years of experience")
    ax.set_ylabel("salary")
    ax.set_title("Fitted line")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    return fig
