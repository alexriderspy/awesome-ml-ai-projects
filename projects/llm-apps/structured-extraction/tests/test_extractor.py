import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from extractor.compare import f1, field_counts, str_match, value_match
from extractor.extract import extract, grounded, parse_json
from extractor.schemas import JobPost, Receipt
from run_eval import path_correct, score

PRACTICE = sorted((ROOT / "eval/practice").glob("*.json"))


class FakeLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    def chat(self, messages, temperature=None):
        self.seen.append(messages)
        return self.replies.pop(0)


def case(name):
    return json.loads((ROOT / f"eval/practice/{name}.json").read_text())


@pytest.mark.parametrize("path", PRACTICE, ids=lambda p: p.stem)
def test_every_gold_answer_passes_its_own_schema(path):
    c = json.loads(path.read_text())
    {"receipt": Receipt, "job_post": JobPost}[c["schema"]].model_validate(c["gold"])


def test_receipt_sum_check_catches_bad_total():
    gold = dict(case("receipt-pizza-sf")["gold"], total=51.05)
    with pytest.raises(ValidationError, match="total is 51.05"):
        Receipt.model_validate(gold)


def test_salary_needs_currency():
    gold = dict(case("job-backend-austin")["gold"], salary_currency=None)
    with pytest.raises(ValidationError, match="salary_currency"):
        JobPost.model_validate(gold)


def test_retry_sends_validation_error_back():
    c = case("receipt-pizza-sf")
    bad = dict(c["gold"], total=51.05)
    llm = FakeLLM(["```json\n" + json.dumps(bad) + "\n```", json.dumps(c["gold"])])
    res = extract(c["text"], "receipt", llm)
    assert res.valid and res.attempts == 2
    assert "total is 51.05" in llm.seen[1][-1]["content"]


def test_gives_up_after_retries():
    llm = FakeLLM(["nope", "still nope", "{}"])
    res = extract("x", "receipt", llm, retries=2)
    assert not res.valid and res.attempts == 3 and len(res.errors) == 3


def test_confidence_uses_grounding_and_agreement():
    c = case("receipt-supermarket-berlin")
    other = dict(c["gold"], merchant="Frischmarkt Berlin-Mitte", payment_method="card")
    llm = FakeLLM([json.dumps(c["gold"]), json.dumps(c["gold"]), json.dumps(other)])
    res = extract(c["text"], "receipt", llm, samples=2)
    conf = res.confidence
    assert conf["total"] == 1.0
    assert conf["payment_method"] == 0.5
    assert conf["date"] == 1.0
    assert "items[2]" in conf


def test_grounded_handles_number_formats():
    assert grounded(1.89, "Bio Bananen 1,89 B")
    assert grounded(150000, "$150,000 – $185,000")
    assert grounded(26.5, "$26.50 per hour")
    assert not grounded(800000, "CTC 8-12 LPA")
    assert grounded("Bean There Cafe", "BEAN THERE CAFE\n14 Mill Lane")
    assert grounded("2025-11-03", "03/11/2025") is None


def test_matching_rules():
    assert str_match("espresso machines", "espresso machine experience")
    assert str_match("Senior Backend Engineer – Payments", "Senior Backend Engineer")
    assert not str_match("Go", "Golang developer tools")
    assert value_match(10.5, 10.50) and not value_match(10.5, 10.6)
    assert value_match(None, None) and not value_match(None, 0)
    assert not value_match("2025-11-03", "2025-03-11")


def test_scorer_counts_lists_per_element():
    gold = case("job-sre-manchester")["gold"]
    pred = dict(gold, skills=["Linux", "Terraform", "AWS"], apply_by=None, location="Manchester")
    counts = field_counts(pred, gold)
    assert counts["skills"] == (3, 3, 6)
    assert counts["apply_by"] == (0, 0, 1)
    p, r, f = f1(counts)
    assert p == 1.0 and r < 1.0
    assert score(gold, gold)["score"] == 100.0
    assert score(None, gold)["score"] == 0.0
    assert path_correct("skills[0]", "linux", gold)


def test_parse_json():
    assert parse_json('Here you go: {"a": 1}') == {"a": 1}
    with pytest.raises(ValueError):
        parse_json("nothing")
