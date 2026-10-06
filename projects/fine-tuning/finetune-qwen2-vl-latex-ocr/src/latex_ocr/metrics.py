import math
import re
from collections import Counter


def normalize(latex: str) -> str:
    s = latex.strip().strip("$").strip()
    s = re.sub(r"\\(displaystyle|textstyle|scriptstyle)\b", "", s)
    s = re.sub(r"\\[,;:! ]|~", "", s)
    s = re.sub(r"\\left|\\right", "", s)
    return re.sub(r"\s+", "", s)


def latex_tokens(latex: str) -> list[str]:
    return re.findall(r"\\[A-Za-z]+|\\.|[A-Za-z0-9]|\S", latex.strip())


def edit_distance(a: list | str, b: list | str) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def normalized_edit_distance(pred: str, ref: str) -> float:
    a, b = normalize(pred), normalize(ref)
    if not a and not b:
        return 0.0
    return edit_distance(a, b) / max(len(a), len(b))


def exact_match(pred: str, ref: str) -> bool:
    return normalize(pred) == normalize(ref)


def _ngrams(toks: list[str], n: int) -> Counter:
    return Counter(tuple(toks[i : i + n]) for i in range(len(toks) - n + 1))


def corpus_bleu(preds: list[str], refs: list[str], max_n: int = 4) -> float:
    match, total = [0] * max_n, [0] * max_n
    pred_len = ref_len = 0
    for p, r in zip(preds, refs):
        pt, rt = latex_tokens(p), latex_tokens(r)
        pred_len += len(pt)
        ref_len += len(rt)
        for n in range(1, max_n + 1):
            pc, rc = _ngrams(pt, n), _ngrams(rt, n)
            match[n - 1] += sum((pc & rc).values())
            total[n - 1] += max(len(pt) - n + 1, 0)
    if pred_len == 0:
        return 0.0
    log_p = sum(math.log((match[i] + 1) / (total[i] + 1)) for i in range(max_n)) / max_n
    bp = 1.0 if pred_len > ref_len else math.exp(1 - ref_len / pred_len)
    return bp * math.exp(log_p)


def score(preds: list[str], refs: list[str]) -> dict:
    em = sum(exact_match(p, r) for p, r in zip(preds, refs)) / len(refs)
    ned = sum(normalized_edit_distance(p, r) for p, r in zip(preds, refs)) / len(refs)
    bleu = corpus_bleu(preds, refs)
    overall = 100 * (0.4 * em + 0.4 * (1 - ned) + 0.2 * bleu)
    return {"exact_match": em, "edit_distance": ned, "bleu": bleu, "overall": round(overall, 1)}
