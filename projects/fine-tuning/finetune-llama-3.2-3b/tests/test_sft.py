import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from finetome_sft.checks import run_check, score_case
from finetome_sft.config import TrainConfig, load_config
from finetome_sft.data import IGNORE, collate, is_valid, sharegpt_to_messages, tokenize_with_mask


class FakeTok:

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False):
        text = "".join(f"<{m['role']}>{m['content']}</s>" for m in messages)
        return text + ("<assistant>" if add_generation_prompt else "")

    def __call__(self, text, add_special_tokens=False):
        return {"input_ids": [ord(c) for c in text]}


def decode(ids):
    return "".join(chr(i) for i in ids)


CONV = [{"from": "human", "value": "Hi "}, {"from": "gpt", "value": "Hello"}, {"from": "human", "value": "Bye"}, {"from": "gpt", "value": "Ciao"}]


def test_sharegpt_roles():
    msgs = sharegpt_to_messages(CONV)
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
    assert msgs[0]["content"] == "Hi"


def test_sharegpt_unknown_role():
    with pytest.raises(ValueError):
        sharegpt_to_messages([{"from": "robot", "value": "x"}])


def test_is_valid():
    assert is_valid(sharegpt_to_messages(CONV))
    assert not is_valid(sharegpt_to_messages(CONV[:3]))
    assert not is_valid([{"role": "assistant", "content": "x"}])
    assert is_valid([{"role": "system", "content": "s"}, {"role": "user", "content": "u"}, {"role": "assistant", "content": "a"}])


def test_mask_covers_only_assistant_turns():
    ex = tokenize_with_mask(FakeTok(), sharegpt_to_messages(CONV), max_len=1000)
    kept = decode([t for t in ex.labels if t != IGNORE])
    assert kept == "Hello</s>Ciao</s>"
    assert len(ex.labels) == len(ex.input_ids)


def test_too_long_is_dropped():
    assert tokenize_with_mask(FakeTok(), sharegpt_to_messages(CONV), max_len=10) is None


def test_collate_pads_and_masks():
    tok = FakeTok()
    a = tokenize_with_mask(tok, sharegpt_to_messages(CONV), 1000)
    b = tokenize_with_mask(tok, sharegpt_to_messages(CONV[:2]), 1000)
    batch = collate([a, b], pad_id=0)
    assert batch["input_ids"].shape == (2, len(a.input_ids))
    assert batch["attention_mask"][1].sum() == len(b.input_ids)
    assert (batch["labels"][1, len(b.input_ids):] == IGNORE).all()


def test_configs_in_repo_are_valid():
    for path in (ROOT / "configs").glob("*.toml"):
        load_config(path)


def test_bad_config_rejected(tmp_path):
    with pytest.raises(ValueError):
        TrainConfig(n_rows=10, n_heldout=20).validate()
    with pytest.raises(ValueError):
        TrainConfig(lr=0.5).validate()
    p = tmp_path / "c.toml"
    p.write_text('modle = "typo"\n')
    with pytest.raises(ValueError, match="unknown config keys"):
        load_config(p)


@pytest.mark.parametrize("kind,arg,text,ok", [
    ("max_words", 3, "one two three", True),
    ("max_words", 2, "one two three", False),
    ("lowercase", None, "all small here.", True),
    ("lowercase", None, "Not small", False),
    ("uppercase", None, "CAUTION: WET FLOOR", True),
    ("bullets", 3, "- a\n- b\n* c", True),
    ("bullets", 3, "- a\n- b", False),
    ("numbered", 2, "1. x\n2) y", True),
    ("json_keys", ["a", "b"], 'Sure: {"a": 1, "b": 2}', True),
    ("json_keys", ["a", "c"], '{"a": 1}', False),
    ("starts_with", "Yes", "yes, it is", True),
    ("ends_with", "Talk soon", "Thanks!\nTalk soon.", True),
    ("no_char", ",", "no commas here", True),
    ("max_sentences", 1, "One. Two.", False),
    ("includes", ["river"], "By the River", True),
    ("excludes", ["cute"], "a cute cat", False),
])
def test_checks(kind, arg, text, ok):
    assert run_check(kind, arg, text) is ok


def test_practice_set_is_well_formed():
    cases = json.loads((ROOT / "eval/practice/checks.json").read_text())
    assert len(cases) == 20 and len({c["id"] for c in cases}) == 20
    for c in cases:
        for chk in c["checks"]:
            run_check(chk["kind"], chk.get("arg"), "probe text")


def test_score_case():
    s, res = score_case({"checks": [{"kind": "lowercase"}, {"kind": "max_words", "arg": 1}]}, "two words")
    assert s == 0.5 and res == [("lowercase", True), ("max_words", False)]


def test_notebook_matches_script():
    nb = json.loads((ROOT / "gpu/finetune_llama_3_2_3b_unsloth.ipynb").read_text())
    code = "".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")
    assert "unsloth/Llama-3.2-3B-Instruct" in code and "load_in_4bit=True" in code
    assert "train_on_responses_only" in code and "FineTome-100k" in code
