import math
import re
from collections import Counter

from .pdf import Chunk

STOP = set("a an the of to in on for and or is are was were be by with at as it this that what which who how when "
           "does do did can i you we they their our your from".split())


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP]


class BM25:
    name = "bm25"

    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks, self.k1, self.b = chunks, k1, b
        self.docs = [Counter(tokenize(c.text)) for c in chunks]
        self.lens = [sum(d.values()) for d in self.docs]
        self.avg = sum(self.lens) / max(len(self.lens), 1)
        df = Counter(t for d in self.docs for t in d)
        n = len(chunks)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: str) -> list[float]:
        q = tokenize(query)
        out = []
        for d, ln in zip(self.docs, self.lens):
            s = 0.0
            for t in q:
                if t in d:
                    tf = d[t]
                    s += self.idf[t] * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * ln / self.avg))
            out.append(s)
        return out

    def search(self, query: str, k: int = 4) -> list[Chunk]:
        sc = self.scores(query)
        order = sorted(range(len(sc)), key=lambda i: -sc[i])
        return [self.chunks[i] for i in order[:k] if sc[i] > 0]


class Embeddings:
    name = "embeddings"

    def __init__(self, chunks: list[Chunk], model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer

        self.chunks = chunks
        self.model = SentenceTransformer(model)
        self.vecs = self.model.encode([c.text for c in chunks], normalize_embeddings=True)

    def search(self, query: str, k: int = 4) -> list[Chunk]:
        q = self.model.encode([query], normalize_embeddings=True)[0]
        sims = self.vecs @ q
        return [self.chunks[i] for i in sims.argsort()[::-1][:k]]


class Hybrid:

    name = "hybrid"

    def __init__(self, chunks: list[Chunk], c: int = 60):
        self.bm25, self.emb, self.c = BM25(chunks), Embeddings(chunks), c

    def search(self, query: str, k: int = 4) -> list[Chunk]:
        fused: dict[int, float] = {}
        by_id = {}
        for ranked in (self.bm25.search(query, k=3 * k), self.emb.search(query, k=3 * k)):
            for rank, ch in enumerate(ranked):
                fused[ch.id] = fused.get(ch.id, 0.0) + 1 / (self.c + rank)
                by_id[ch.id] = ch
        return [by_id[i] for i in sorted(fused, key=lambda i: -fused[i])[:k]]


def make_retriever(chunks: list[Chunk], method: str = "auto"):
    try:
        if method in ("auto", "hybrid"):
            return Hybrid(chunks)
        if method == "embeddings":
            return Embeddings(chunks)
    except ImportError:
        if method != "auto":
            raise
    return BM25(chunks)
