import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ticket_router.data import DATA, load_jsonl, load_split, parse_label, sft_messages, stratified_split
from ticket_router.labels import LABELS
from ticket_router.metrics import accuracy, confusion, macro_f1, percentile


def test_parse_label():
    assert parse_label("billing") == "billing"
    assert parse_label("  `login access`.") == "login_access"
    assert parse_label("I think this is a bug_report, not billing") == "bug_report"
    assert parse_label("no idea") is None


def test_split_is_stratified_and_disjoint():
    rows = load_jsonl(DATA / "tickets.jsonl")
    split = stratified_split(rows, n_val=13, n_test=12)
    ids = split["train"] + split["val"] + split["test"]
    assert len(ids) == len(set(ids)) == len(rows)
    test = load_split("test")
    assert all(sum(r["label"] == l for r in test) == 12 for l in LABELS)


def test_sft_messages_end_with_label():
    msgs = sft_messages({"text": "I was charged twice", "label": "billing"})
    assert msgs[-1] == {"role": "assistant", "content": "billing"}


def test_metrics():
    gold = ["billing", "billing", "performance"]
    pred = ["billing", None, "performance"]
    assert accuracy(gold, pred) == 2 / 3
    assert 0 < macro_f1(gold, pred) < 1
    assert confusion(gold, pred)[LABELS.index("billing")][-1] == 1
    assert percentile([1, 2, 3, 4], 50) == 2
