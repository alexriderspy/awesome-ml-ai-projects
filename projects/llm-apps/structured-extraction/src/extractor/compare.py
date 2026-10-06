import re

STOP = {"a", "an", "the", "of", "and", "with", "in", "for", "experience", "knowledge", "skills", "co", "inc", "ltd", "x"}
LIST_FIELDS = ("items", "skills")


def tokens(s: str) -> set[str]:
    out = set()
    for t in re.findall(r"[a-z0-9]+", str(s).lower()):
        if t in STOP:
            continue
        if len(t) > 3 and t.endswith("s"):
            t = t[:-1]
        out.add(t)
    return out


def str_match(a: str, b: str) -> bool:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return str(a).strip().lower() == str(b).strip().lower()
    short, long_ = sorted((ta, tb), key=len)
    if short <= long_ and len(long_) <= 2 * len(short):
        return True
    return len(ta & tb) / len(long_) >= 0.6


def is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def value_match(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if is_num(a) and is_num(b):
        return abs(float(a) - float(b)) <= 0.011
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    a, b = str(a), str(b)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", a) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", b):
        return a == b
    return str_match(a, b)


def item_match(p: dict, g: dict) -> bool:
    return (str_match(p.get("name", ""), g.get("name", ""))
            and value_match(float(p.get("quantity") or 1), float(g.get("quantity") or 1))
            and value_match(p.get("total"), g.get("total")))


def _greedy(pred: list, gold: list, match) -> int:
    used, tp = set(), 0
    for g in gold:
        for i, p in enumerate(pred):
            if i not in used and match(p, g):
                used.add(i)
                tp += 1
                break
    return tp


def field_counts(pred: dict | None, gold: dict) -> dict:
    pred = pred or {}
    out = {}
    for key, gv in gold.items():
        pv = pred.get(key)
        if key == "items":
            pv = pv or []
            out[key] = (_greedy(pv, gv, item_match), len(pv), len(gv))
        elif key == "skills":
            pv = pv or []
            out[key] = (_greedy(pv, gv, str_match), len(pv), len(gv))
        else:
            n_pred, n_gold = int(pv is not None), int(gv is not None)
            tp = int(n_pred and n_gold and value_match(pv, gv))
            out[key] = (tp, n_pred, n_gold)
    return out


def f1(counts: dict) -> tuple[float, float, float]:
    tp = sum(c[0] for c in counts.values())
    n_pred = sum(c[1] for c in counts.values())
    n_gold = sum(c[2] for c in counts.values())
    p = tp / n_pred if n_pred else 0.0
    r = tp / n_gold if n_gold else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)
