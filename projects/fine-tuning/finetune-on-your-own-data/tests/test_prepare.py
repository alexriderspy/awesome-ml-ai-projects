import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from own_data_sft.prepare import Pair, Rules, build, dedupe, length_ok, scrub, split
from own_data_sft.train import with_system
from run_eval import score, token_f1


def test_scrub_replaces_pii_and_names():
    text, hits = scrub("Mail lena@example.com or call 07700 900123, Lena", {"Lena Ortiz"})
    assert "lena@example.com" not in text and "07700" not in text and "Lena" not in text
    assert hits["[EMAIL]"] == 1 and hits["[PHONE]"] == 1 and hits["[NAME]"] == 1


def test_dedupe_drops_exact_and_near():
    long = "We open at ten in the morning from Tuesday to Saturday and close at nine in the evening, and we are closed on Sundays and Mondays all year round"
    pairs = [Pair("What time do you open?", long + ".", "faq"),
             Pair("what time do you open", long, "faq"),
             Pair("What time do you open?", long + " except holidays.", "faq"),
             Pair("Where are you?", "Behind the old harbour, blue door.", "faq")]
    kept, dropped = dedupe(pairs, 0.8)
    assert len(kept) == 2
    assert dropped["exact_duplicate"] == 1 and dropped["near_duplicate"] == 1


def test_length_rules():
    r = Rules()
    assert length_ok(Pair("hi", "hello there friend ok", "x"), r) == "instruction_too_short"
    assert length_ok(Pair("how are you today", "fine", "x"), r) == "response_too_short"


def test_split_is_stable():
    pairs = [Pair(f"question number {i} here", "answer text goes here", "faq") for i in range(50)]
    a = split(pairs, 0.2, 0)
    b = split(pairs + [Pair("a brand new question", "with its answer here", "faq")], 0.2, 0)
    assert set(p.instruction for p in a[1]) <= set(p.instruction for p in b[1])


def test_build_on_sample_data(tmp_path):
    report = build(ROOT / "data/raw", tmp_path)
    assert report["train"] > 0 and report["val"] > 0
    rows = [json.loads(l) for l in (tmp_path / "train.jsonl").read_text().splitlines()]
    assert all(r["messages"][-1]["role"] == "assistant" for r in rows)
    assert not any("[CARD]" in json.dumps(r) for r in rows)


def test_with_system_prepends_once():
    msgs = [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]
    assert with_system(msgs, "sys")[0] == {"role": "system", "content": "sys"}
    assert with_system(with_system(msgs, "sys"), "sys")[1]["role"] == "user"


def test_eval_score():
    ref = "The beginner course costs £210 for six sessions."
    assert token_f1(ref, ref) == 1.0
    assert score("It costs £210 for six sessions.", ref) > score("It is free.", ref)
