import json
import random
from collections import defaultdict
from pathlib import Path

from .labels import LABELS, category_block

DATA = Path(__file__).resolve().parents[2] / "data"

INSTRUCTION = "Route this support ticket for Tallyo (invoicing app) to one category. Reply with the category name only."


def load_jsonl(path: str | Path) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def stratified_split(rows: list[dict], n_val: int, n_test: int, seed: int = 0) -> dict[str, list[str]]:
    by_label = defaultdict(list)
    for r in rows:
        by_label[r["label"]].append(r["id"])
    rng = random.Random(seed)
    split = {"train": [], "val": [], "test": []}
    for label in sorted(by_label):
        ids = sorted(by_label[label])
        rng.shuffle(ids)
        split["val"] += ids[:n_val]
        split["test"] += ids[n_val:n_val + n_test]
        split["train"] += ids[n_val + n_test:]
    return split


def load_split(name: str) -> list[dict]:
    rows = {r["id"]: r for r in load_jsonl(DATA / "tickets.jsonl")}
    ids = json.loads((DATA / "splits.json").read_text())[name]
    return [rows[i] for i in ids]


def short_prompt(text: str) -> str:
    return f"{INSTRUCTION}\nCategories: {', '.join(LABELS)}\n\nTicket:\n{text.strip()}"


def zero_shot_prompt(text: str) -> str:
    return f"{INSTRUCTION}\n\nCategories:\n{category_block()}\n\nTicket:\n{text.strip()}"


def sft_messages(row: dict) -> list[dict]:
    return [{"role": "user", "content": short_prompt(row["text"])}, {"role": "assistant", "content": row["label"]}]


def parse_label(text: str) -> str | None:
    t = text.strip().lower().strip("`'\". \n")
    if t in LABELS:
        return t
    t2 = t.replace(" ", "_").replace("-", "_")
    hits = [(t2.find(l), l) for l in LABELS if l in t2]
    return min(hits)[1] if hits else None
