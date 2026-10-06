import json
import math
import re
from collections import Counter
from pathlib import Path

DEFAULT_SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "issues.json"

STOPWORDS = set(
    "a an and are as at be but by can do does for from has have how i if in is it its me my no not of on or "
    "so that the then there this to was we what when which while with would you your".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9_]+", text.lower()) if t not in STOPWORDS and len(t) > 1]


class BM25:
    def __init__(self, docs: dict[int, list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = {key: Counter(toks) for key, toks in docs.items()}
        self.len = {key: len(toks) for key, toks in docs.items()}
        self.avgdl = sum(self.len.values()) / max(1, len(docs))
        df = Counter(t for toks in docs.values() for t in set(toks))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def score(self, query: list[str], key: int) -> float:
        tf, dl, s = self.tf[key], self.len[key], 0.0
        for t in set(query):
            f = tf.get(t, 0)
            if f:
                s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
        return s

    def search(self, query: str, k: int = 5, exclude: set[int] = frozenset()) -> list[tuple[int, float]]:
        q = tokenize(query)
        scored = [(key, self.score(q, key)) for key in self.tf if key not in exclude]
        scored = [x for x in scored if x[1] > 0]
        return sorted(scored, key=lambda x: (-x[1], x[0]))[:k]


class Snapshot:
    def __init__(self, data: dict):
        self.project = data["project"]
        self.label_set: list[str] = data["labels"]
        self.issues: dict[int, dict] = {i["number"]: i for i in data["issues"]}
        self.index = BM25({n: tokenize(i["title"]) * 2 + tokenize(i["body"]) for n, i in self.issues.items()})

    @classmethod
    def load(cls, path: str | Path = DEFAULT_SNAPSHOT) -> "Snapshot":
        return cls(json.loads(Path(path).read_text()))

    def untriaged(self) -> list[int]:
        return sorted(n for n, i in self.issues.items() if not i["labels"])
