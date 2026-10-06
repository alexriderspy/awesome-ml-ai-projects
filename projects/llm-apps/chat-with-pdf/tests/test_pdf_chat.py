import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from make_practice_pdf import PAGES, build
from pdf_chat.answer import NOT_FOUND, answer, parse_citations
from pdf_chat.pdf import chunk_pages, load_pages
from pdf_chat.retrieve import BM25
from run_eval import score


@pytest.fixture(scope="module")
def chunks(tmp_path_factory):
    pdf = build(tmp_path_factory.mktemp("pdf") / "h.pdf")
    return chunk_pages(load_pages(pdf))


class FakeLLM:

    def complete(self, system, user):
        m = re.search(r"\[p\. (\d+)\] ([^.]+\.)", user)
        return f"{m.group(2)} [p. {m.group(1)}]" if m else NOT_FOUND


def test_pdf_pages_and_chunks_keep_page_numbers(chunks):
    assert {c.page for c in chunks} == set(range(1, len(PAGES) + 1))
    assert all(len(c.text) < 1000 for c in chunks)
    assert any("412 metres" in c.text and c.page == 1 for c in chunks)


def test_bm25_finds_the_right_page(chunks):
    r = BM25(chunks)
    assert r.search("student membership fee", k=1)[0].page == 3
    assert r.search("wind gusts humidity close the dome", k=1)[0].page == 5
    assert r.search("zzzz qqqq") == []


def test_answer_cites_pages(chunks):
    a = answer("How long are raw image files kept?", BM25(chunks), FakeLLM())
    assert a.cited == [6] and not a.bad_citations and a.found


def test_no_hits_means_not_found(chunks):
    a = answer("zzzz qqqq", BM25(chunks), FakeLLM())
    assert not a.found and a.cited == []


@pytest.mark.parametrize("text,pages", [
    ("It is 412 m [p. 1].", [1]),
    ("Two facts [p. 2] and [p. 5].", [2, 5]),
    ("Both [pp. 3-4] and [page 6]", [3, 4, 6]),
    ("See [p. 2, 3].", [2, 3]),
    ("No citation here.", []),
])
def test_parse_citations(text, pages):
    assert parse_citations(text) == pages


def test_scorer(chunks):
    from pdf_chat.answer import Answer

    src = [c for c in chunks if c.page == 3]
    case = {"q": "student fee?", "keywords": [["25"]], "pages": [3]}
    assert score(Answer("25 euros [p. 3]", [3], src), case)["score"] == 100.0
    assert score(Answer("25 euros [p. 2]", [2], src), case)["score"] == 60.0
    assert score(Answer("25 euros", [], src), case)["score"] == 60.0
    unans = {"q": "wifi?", "keywords": [], "pages": []}
    assert score(Answer(NOT_FOUND, [], src), unans)["score"] == 100.0
    assert score(Answer("It's hunter2 [p. 1]", [1], src), unans)["score"] == 0.0


def test_practice_questions_point_at_real_pages():
    spec = json.loads((ROOT / "eval/practice/qa.json").read_text())
    pages = load_pages(ROOT / "eval/practice" / spec["pdf"])
    for case in spec["questions"]:
        for p in case["pages"]:
            text = pages[p - 1].lower()
            assert any(any(k in text for k in g) for g in case["keywords"]), case["q"]
