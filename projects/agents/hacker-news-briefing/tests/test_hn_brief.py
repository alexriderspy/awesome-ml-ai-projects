import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from hn_brief import slack
from hn_brief.brief import to_slack_text, write
from hn_brief.hn import HNClient, Story, html_to_text
from hn_brief.pipeline import load_snapshot, run, save_snapshot
from hn_brief.profile import Profile, load_profile
from hn_brief.rank import count_phrase, llm_rerank, rank, tokens
from hn_brief.summarize import summarize_one
from run_eval import format_ok, key_terms, load_cases, ndcg_at_k, term_coverage

FIX = ROOT / "tests" / "fixtures"
API = json.loads((FIX / "api.json").read_text())
PAGE_URL = "https://blog.example.org/planner"


class Resp:
    def __init__(self, data=None, text="", ctype="application/json"):
        self._data, self.text, self.headers = data, text, {"Content-Type": ctype}

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


class FakeGet:

    def __init__(self):
        self.calls = []

    def __call__(self, url, timeout=None):
        self.calls.append(url)
        assert timeout is not None, "every request needs a timeout"
        if url in API:
            return Resp(API[url])
        if url == PAGE_URL:
            return Resp(text=(FIX / "page.html").read_text(), ctype="text/html; charset=utf-8")
        if url.endswith(".pdf"):
            return Resp(text="%PDF-1.7", ctype="application/pdf")
        raise ConnectionError(f"offline: {url}")


class FakeLLM:
    def __init__(self, rerank_reply=None):
        self.calls = []
        self.rerank_reply = rerank_reply

    def complete(self, system, user):
        self.calls.append((system, user))
        if "rank Hacker News" in system:
            return self.rerank_reply or "{}"
        title = user.split("Title: ", 1)[1].split("\n", 1)[0]
        return json.dumps({"summary": f"{title}. It explains the details.", "why": "You run this in production."})


PROFILE = Profile.from_dict({
    "name": "Tester",
    "interests": [{"name": "databases", "weight": 3, "keywords": ["postgres", "sqlite", "query planner"]},
                  {"name": "hardware", "weight": 1, "keywords": ["gpu"]}],
    "dislikes": ["bitcoin"],
})


def test_top_stories_skips_jobs_and_dead_items():
    stories = HNClient(get=FakeGet()).top_stories(10)
    assert [s.id for s in stories] == [101, 102, 105]
    assert stories[0].domain == "blog.example.org"
    assert stories[0].kids == [201, 202, 203]
    assert stories[2].text.startswith("We run SQLite on three edge boxes.")
    assert stories[2].hn_url.endswith("id=105")


def test_top_comments_skip_deleted_and_strip_html():
    c = HNClient(get=FakeGet())
    s = c.top_stories(1)[0]
    got = c.top_comments(s, k=2)
    assert got == ["The enable_hashjoin trick saved us > 40% on one report. Measure first though.",
                   "Extended statistics are the underrated part."]


def test_page_text_drops_scripts_and_chrome():
    text = HNClient(get=FakeGet()).page_text(PAGE_URL)
    assert "Extended statistics fix correlated columns." in text
    assert "tracking" not in text and "Home | About" not in text and "color:red" not in text


def test_page_text_is_best_effort():
    c = HNClient(get=FakeGet())
    assert c.page_text("https://unreachable.example/x") == ""
    assert c.page_text("https://papers.example/x.pdf") == ""
    assert c.page_text("ftp://old.example/file") == ""


def test_enrich_survives_failures():
    c = HNClient(get=FakeGet())
    stories = c.top_stories(10)
    stories[1].url = "https://unreachable.example/miners"
    c.enrich(stories)
    assert stories[0].page_text and len(stories[0].top_comments) == 2
    assert stories[1].page_text == "" and stories[1].top_comments == []


def test_html_to_text_entities():
    assert html_to_text("a &amp; b<p>c") == "a & b c"


def test_tokens_and_phrases():
    assert tokens("Node.js GPUs and C++") == ["node.js", "gpu", "and", "c++"]
    assert count_phrase(tokens("query planner"), tokens("The query planners and the query planner")) == 2


def test_rank_prefers_interests_and_buries_dislikes():
    stories = HNClient(get=FakeGet()).top_stories(10)
    ranked = rank(stories, PROFILE)
    ids = [r.story.id for r in ranked]
    assert ids[-1] == 102
    assert ranked[-1].disliked == ["bitcoin"]
    assert ranked[0].story.id == 101 and ranked[0].matches["databases"][0] in ("postgres", "query planner")


def test_popularity_prior_breaks_ties():
    a = Story(1, "Untitled thing", score=5, comments=0)
    b = Story(2, "Another thing", score=900, comments=400)
    assert [r.story.id for r in rank([a, b], PROFILE)] == [2, 1]


def test_llm_rerank_reorders_head_only():
    stories = HNClient(get=FakeGet()).top_stories(10)
    ranked = rank(stories, PROFILE)
    llm = FakeLLM(rerank_reply='{"scores": {"105": 9, "101": 4}}')
    out = llm_rerank(ranked, PROFILE, llm, top_n=2)
    assert [r.story.id for r in out[:2]] == [105, 101]
    assert out[2].story.id == ranked[2].story.id
    assert "does NOT want: bitcoin" in llm.calls[0][1]


def test_llm_rerank_falls_back_on_garbage():
    ranked = rank(HNClient(get=FakeGet()).top_stories(10), PROFILE)
    before = [r.story.id for r in ranked]
    out = llm_rerank(ranked, PROFILE, FakeLLM(rerank_reply="sorry, I can't"))
    assert [r.story.id for r in out] == before


def test_summarize_parses_json_and_falls_back():
    r = rank([Story(1, "Postgres 19 is out")], PROFILE)[0]
    e = summarize_one(r, PROFILE, FakeLLM())
    assert e.summary.startswith("Postgres 19 is out.") and e.why

    class Plain:
        def complete(self, s, u):
            return "One. Two. Three. Four."

    e2 = summarize_one(r, PROFILE, Plain())
    assert e2.summary == "One. Two. Three." and e2.why == ""


def test_pipeline_end_to_end_offline(tmp_path):
    get = FakeGet()
    client = HNClient(get=get)
    res = run(PROFILE, FakeLLM('{"scores": {"105": 10, "101": 8, "102": 0}}'), client=client, top_k=2,
              rerank=True, comments=True, pages=True, day=date(2026, 10, 6))
    assert [e.ranked.story.id for e in res.entries] == [105, 101]
    md = res.markdown
    assert md.startswith("# Hacker News brief - 2026-10-06")
    assert "## 1. [Ask HN: Which SQLite backup strategy do you trust?]" in md
    assert "**Why it matters to you:** You run this in production." in md
    assert "Bitcoin miners" in md.split("## Also on the front page")[1]
    assert PAGE_URL in get.calls
    path = write(md, tmp_path / "briefs", date(2026, 10, 6))
    assert path.name == "2026-10-06.md" and path.read_text() == md


def test_snapshot_roundtrip(tmp_path):
    stories = HNClient(get=FakeGet()).top_stories(10)
    save_snapshot(stories, tmp_path / "s.json")
    again = load_snapshot(tmp_path / "s.json")
    assert [(s.id, s.title, s.score) for s in again] == [(s.id, s.title, s.score) for s in stories]


def test_profile_yaml_loads():
    p = load_profile(ROOT / "profiles" / "example.yaml")
    assert p.interests and p.interests[0].keywords


def test_slack_posts_json_to_webhook():
    sent = []

    def post(url, json=None, timeout=None):
        sent.append((url, json, timeout))
        return Resp()

    r = rank([Story(1, "Postgres 19 is out", url="https://pg.example/19")], PROFILE)[0]
    text = to_slack_text([summarize_one(r, PROFILE, FakeLLM())], date(2026, 10, 6))
    assert slack.send(text, "https://hooks.slack.com/services/T0/B0/x", post=post)
    assert sent[0][0].startswith("https://hooks.slack.com/") and "<https://pg.example/19|Postgres 19 is out>" in sent[0][1]["text"]


def test_slack_refuses_other_urls(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    with pytest.raises(ValueError):
        slack.send("hi", post=lambda *a, **k: pytest.fail("should not post"))
    with pytest.raises(ValueError):
        slack.send("hi", "https://evil.example/hook", post=lambda *a, **k: pytest.fail("should not post"))


def test_cli_does_not_send_without_flag(monkeypatch, tmp_path):
    import hn_brief.__main__ as cli

    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T0/B0/x")
    monkeypatch.setattr(cli.slack, "send", lambda *a, **k: pytest.fail("sent without --send-slack"))
    monkeypatch.setattr(cli, "OpenAICompatible", lambda: FakeLLM())
    snap = tmp_path / "s.json"
    save_snapshot(HNClient(get=FakeGet()).top_stories(10), snap)
    monkeypatch.setattr(sys, "argv", ["hn_brief", "--profile", str(ROOT / "profiles" / "example.yaml"),
                                      "--snapshot", str(snap), "--out", str(tmp_path / "briefs"), "--top", "2"])
    cli.main()
    assert len(list((tmp_path / "briefs").glob("*.md"))) == 1


def test_ndcg():
    gold = {1: 2, 2: 1}
    assert ndcg_at_k([1, 2, 3], gold) == pytest.approx(1.0)
    assert ndcg_at_k([3, 2, 1], gold) < ndcg_at_k([2, 1, 3], gold) < 1.0
    assert ndcg_at_k([3, 4], gold) == 0.0


def test_format_and_terms():
    assert format_ok("One. Two.", "You care.") == 1.0
    assert format_ok("One. Two. Three. Four.", "") == 0.0
    assert key_terms("Show HN: A SQLite extension for vector search") == ["extension", "sqlite", "vector", "search"]
    assert term_coverage("A SQLite extension adds vector search.", "Show HN: A SQLite extension for vector search") == 1.0


def test_practice_set_and_bm25_baseline():
    cases = load_cases()
    assert len(cases) == 8
    mean = sum(ndcg_at_k([r.story.id for r in rank(c["stories"], c["profile"])], c["gold"]) for c in cases) / len(cases)
    assert mean > 0.9
