import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from run_eval import field_f1, norm, pagination_score, score_site, serve
from scrape_agent.agent import ScrapeSession, run_agent
from scrape_agent.clean import clean_html
from scrape_agent.fetch import HttpFetcher
from scrape_agent.schema import generate_schema, normalize_schema, validate_record

SITES = ROOT / "eval" / "sites"
CATALOG = json.loads((SITES / "catalog" / "gold.json").read_text())


def site_fetcher(site: str, base: str = "http://test.local"):
    pages = {f"{base}/{site}/{p.name}": p.read_text() for p in (SITES / site).glob("*.html")}

    def fetch(url):
        if url not in pages:
            raise FileNotFoundError(url)
        return pages[url]
    return fetch


class ScriptedLLM:

    def __init__(self, turns, schema_reply=None):
        self.turns = list(turns)
        self.schema_reply = schema_reply
        self.seen = []

    def complete(self, system, user):
        return self.schema_reply

    def chat(self, messages, tools=None):
        self.seen.append(messages[-1])
        if not self.turns:
            return {"content": "done", "tool_calls": []}
        calls = self.turns.pop(0)
        return {"content": "", "tool_calls": [{"id": f"c{i}", "name": n, "arguments": a} for i, (n, a) in enumerate(calls)]}


def test_cleaner_drops_chrome_and_keeps_content():
    html = """<html><head><title> Shop </title><style>.x{}</style><script>var a=1</script></head><body>
    <nav class="main"><a href="/a">Menu</a></nav><div class="cookie-banner">cookies!</div>
    <div style="display:none">secret draft</div>
    <h2>Item <a href="/p/1">One</a></h2><p>Price <s>$9</s> $7</p>
    <nav class="pagination"><a href="?page=2" rel="next">Next</a></nav>
    <footer>footer text</footer></body></html>"""
    page = clean_html(html, "https://shop.test/list")
    md = page.markdown
    assert page.title == "Shop"
    for gone in ("var a", "Menu", "cookies", "secret draft", "footer text", ".x{}"):
        assert gone not in md
    assert "## Item [One](https://shop.test/p/1)" in md
    assert "~~$9~~ $7" in md
    assert page.next_candidates()[0]["url"] == "https://shop.test/list?page=2"


def test_cleaner_renders_tables_as_markdown():
    page = clean_html("<table><tr><th>A</th><th>B</th></tr><tr><td><a href='/x'>x</a></td><td>1 | 2</td></tr></table>",
                      "http://h/")
    assert "| A | B |" in page.markdown
    assert "| [x](http://h/x) | 1 / 2 |" in page.markdown


def test_cleaner_handles_nested_dropped_divs():
    html = '<div class="ad-slot"><div><div>ad</div></div>still ad</div><p>keep me</p>'
    md = clean_html(html).markdown
    assert "ad" not in md and "keep me" in md


def test_next_candidates_ignore_long_read_more_links():
    page = clean_html('<a href="/docs">Read more about publishing your package</a><a href="/p2">Load more</a>', "http://h/")
    assert [c["url"] for c in page.next_candidates()] == ["http://h/p2"]


def test_normalize_schema_picks_key_and_types():
    s = normalize_schema('{"type":"array","items":{"properties":{"name":{"type":"string"},"price":{"type":["number","null"]}}}}')
    assert s["key"] == "name" and s["required"] == ["name"]
    assert s["properties"]["price"]["type"] == "number"


def test_validate_record_coerces_and_rejects():
    s = normalize_schema(CATALOG["schema"])
    ok, errs = validate_record({"name": "Trowel", "price": "1,036.00", "in_stock": "yes", "extra": 1}, s)
    assert errs == [] and ok == {"name": "Trowel", "price": 1036.0, "in_stock": True}
    bad, errs = validate_record({"price": "$5"}, s)
    assert bad is None and any("name: required" in e for e in errs) and any("price" in e for e in errs)


def test_generate_schema_from_model_reply():
    reply = '```json\n{"type":"object","properties":{"title":{"type":"string"},"stars":{"type":"integer"}},"key":"title"}\n```'
    s = generate_schema("repo names and stars", ScriptedLLM([], schema_reply=reply))
    assert s["key"] == "title" and s["properties"]["stars"]["type"] == "integer"


def test_session_tools_cap_pages_and_dedupe():
    sess = ScrapeSession(normalize_schema(CATALOG["schema"]), site_fetcher("catalog"), max_pages=2)
    out = sess.fetch_page("http://test.local/catalog/page1.html")
    assert "Cedar Raised Bed Kit" in out and "catalog/page2.html" in out.split("NEXT PAGE")[1]
    assert "Already fetched" in sess.fetch_page("http://test.local/catalog/page1.html")
    assert "ERROR" in sess.fetch_page("http://test.local/catalog/nope.html")
    sess.fetch_page("http://test.local/catalog/page2.html")
    assert "Page cap" in sess.fetch_page("http://test.local/catalog/page3.html")
    msg = sess.save_records([{"name": "A", "price": 1}, {"name": "a ", "price": 2}, {"price": 3}])
    assert msg.startswith("Saved 1, skipped 1 duplicates, rejected 1")
    assert sess.pages == ["http://test.local/catalog/page1.html", "http://test.local/catalog/page2.html"]


def _gold_turns(case, site, base="http://test.local"):
    turns = []
    per_page = len(case["records"]) // len(case["pages"])
    for i, page in enumerate(case["pages"]):
        turns.append([("fetch_page", {"url": f"{base}/{site}/{page}"})])
        recs = case["records"][i * per_page:] if i == len(case["pages"]) - 1 else case["records"][i * per_page:(i + 1) * per_page]
        turns.append([("save_records", {"records": recs})])
    turns.append([("finish", {"summary": "ok"})])
    return turns


def test_agent_loop_with_scripted_model_scores_perfectly():
    llm = ScriptedLLM(_gold_turns(CATALOG, "catalog"))
    res = run_agent("http://test.local/catalog/page1.html", CATALOG["description"], llm,
                    schema=CATALOG["schema"], fetcher=site_fetcher("catalog"))
    assert res.stop_reason == "finished" and len(res.pages) == 3
    assert [e["tool"] for e in res.log] == ["fetch_page", "save_records"] * 3 + ["finish"]
    assert res.log[1]["args"] == {"records": "<6 records>"}
    s = score_site(res, CATALOG, "catalog")
    assert s["f1"] == 1.0 and s["pagination"] == 1.0


def test_agent_stops_at_step_cap_and_on_silence():
    looping = ScriptedLLM([[("fetch_page", {"url": "http://test.local/x"})]] * 50)
    res = run_agent("u", "d", looping, schema=CATALOG["schema"], fetcher=site_fetcher("catalog"), max_steps=4)
    assert res.steps == 4 and res.stop_reason == "step cap reached"
    silent = ScriptedLLM([])
    res = run_agent("u", "d", silent, schema=CATALOG["schema"], fetcher=site_fetcher("catalog"))
    assert res.stop_reason == "model stopped calling tools" and res.steps == 2
    assert "Use the tools" in silent.seen[-1]["content"]


def test_real_httpx_fetch_against_local_server():
    server, base = serve(SITES)
    try:
        html = HttpFetcher()(f"{base}/events/page1.html")
        assert "Seed Swap" in html
        with pytest.raises(ValueError):
            HttpFetcher()(f"{base}/events/gold.json")
    finally:
        server.shutdown()


def test_norm_and_field_f1():
    assert norm("$x") == "$x" and norm(" Kettle  &  Co ") == "kettle & co"
    assert norm("1,200") == norm(1200) == 1200.0
    assert norm("http://127.0.0.1:9/posts/a.html") == norm("/posts/a.html")
    gold = [{"k": "a", "v": 1}, {"k": "b", "v": 2}]
    assert field_f1(gold, gold, ["k", "v"], "k")["f1"] == 1.0
    half = field_f1([{"k": "a", "v": 1}], gold, ["k", "v"], "k")
    assert half["precision"] == 1.0 and half["recall"] == 0.5
    wrong = field_f1([{"k": "a", "v": 9}, {"k": "zzz", "v": 2}], gold, ["k", "v"], "k")
    assert wrong["precision"] == 0.25


def test_pagination_score():
    assert pagination_score(["http://h/jobs/page1.html"], ["page1.html", "page2.html"], "jobs") == 0.5


@pytest.mark.parametrize("site", sorted(p.name for p in SITES.iterdir() if (p / "gold.json").exists()))
def test_gold_records_validate_and_appear_on_pages(site):
    case = json.loads((SITES / site / "gold.json").read_text())
    schema = normalize_schema(case["schema"])
    text = " ".join(clean_html((SITES / site / p).read_text()).markdown for p in case["pages"])
    for rec in case["records"]:
        assert validate_record(rec, schema)[1] == []
        assert str(rec[schema["key"]]) in text


def test_cleaner_keeps_rating_classes_and_full_titles():
    html = '<p class="star-rating Four"></p><h3><a href="/b" title="A Long Book Title Here">A Long Book ...</a></h3>'
    md = clean_html(html, "http://h/").markdown
    assert "[star-rating Four]" in md and "[A Long Book Title Here](http://h/b)" in md
