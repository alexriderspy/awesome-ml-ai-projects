from .labels import LABELS


def accuracy(gold: list[str], pred: list[str | None]) -> float:
    return sum(g == p for g, p in zip(gold, pred)) / len(gold)


def macro_f1(gold: list[str], pred: list[str | None], labels: list[str] = LABELS) -> float:
    f1s = []
    for l in labels:
        tp = sum(g == l and p == l for g, p in zip(gold, pred))
        fp = sum(g != l and p == l for g, p in zip(gold, pred))
        fn = sum(g == l and p != l for g, p in zip(gold, pred))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return sum(f1s) / len(f1s)


def confusion(gold: list[str], pred: list[str | None], labels: list[str] = LABELS) -> list[list[int]]:
    idx = {l: i for i, l in enumerate(labels)}
    m = [[0] * (len(labels) + 1) for _ in labels]
    for g, p in zip(gold, pred):
        m[idx[g]][idx.get(p, len(labels))] += 1
    return m


def percentile(xs: list[float], q: float) -> float:
    s = sorted(xs)
    if not s:
        return 0.0
    k = max(0, min(len(s) - 1, int(round(q / 100 * len(s) + 0.5)) - 1))
    return s[k]
