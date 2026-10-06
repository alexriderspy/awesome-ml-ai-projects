import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latex_ocr.data import INSTRUCTION, prompt_messages, to_conversation
from latex_ocr.metrics import corpus_bleu, edit_distance, exact_match, latex_tokens, normalize, normalized_edit_distance, score


def test_normalize_ignores_spacing_commands():
    assert normalize(r"$\frac{a}{b} \, + \left( c \right)$") == normalize(r"\frac{a}{b}+(c)")


def test_exact_match_and_edit_distance():
    assert exact_match(r"x^{2} + y", r"x^{2}+y")
    assert edit_distance("kitten", "sitting") == 3
    assert normalized_edit_distance("abc", "abc") == 0.0
    assert normalized_edit_distance("abc", "xyz") == 1.0


def test_tokens_keep_commands_whole():
    assert latex_tokens(r"\alpha_{1}") == ["\\alpha", "_", "{", "1", "}"]


def test_bleu_bounds():
    refs = [r"\frac{a}{b}", r"\sum_{i=1}^{n} i"]
    assert corpus_bleu(refs, refs) == pytest.approx(1.0)
    assert corpus_bleu(["zzz", "qqq"], refs) < 0.2


def test_score_perfect_is_100():
    refs = [r"E=mc^{2}", r"\sqrt{x}"]
    assert score(refs, refs)["overall"] == 100.0


def test_conversation_format():
    conv = to_conversation({"image": "IMG", "text": r"\pi"})["messages"]
    assert conv[0]["content"][0]["text"] == INSTRUCTION
    assert conv[0]["content"][1] == {"type": "image", "image": "IMG"}
    assert conv[1]["content"][0]["text"] == r"\pi"
    assert prompt_messages()[0]["content"][0]["type"] == "image"
