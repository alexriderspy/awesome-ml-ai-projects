import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from blog_writer import checks
from blog_writer.search import CachedSearch, html_to_text
from blog_writer.swarm import Agent, Result, function_schema, run
from blog_writer.team import write_post
from run_eval import citation_validity, fact_coverage, score

FIXTURE = ROOT / "tests/fixtures/search-sundials.json"

DRAFT = """# Reading Time From a Shadow

Sundials are the oldest clocks we still build [1].

## The gnomon

The shadow of the gnomon sweeps across hour lines [1]. It must point at the celestial pole, at an angle equal to your latitude [2].

## Sun time is not clock time

Apparent solar time can be about 16 minutes off clock time; the fix is the equation of time [3].

## Conclusion

A sundial needs only a shadow and a correction table [1][3].
"""


class ScriptedLLM:
    """Plays back tool calls by active agent (read from the system prompt)."""

    def __init__(self, script: dict[str, list]):
        self.script = {k: list(v) for k, v in script.items()}
        self.seen_tools: list[list[str]] = []
        self.n = 0

    def chat(self, messages, tools=None):
        self.n += 1
        self.seen_tools.append([t["function"]["name"] for t in tools or []])
        agent = messages[0]["content"].split(".")[0].removeprefix("You are ")
        step = self.script[agent].pop(0)
        if isinstance(step, str):
            return {"content": step, "tool_calls": [], "reasoning": None}
        calls = [{"id": f"c{self.n}_{i}", "name": n, "arguments": a} for i, (n, a) in enumerate(step)]
        return {"content": "", "tool_calls": calls, "reasoning": None}


def happy_script(revise: bool = False) -> dict:
    editor = [[("check_draft", {})]]
    writer = [[("save_draft", {"markdown": DRAFT}), ("transfer_to_editor", {})]]
    if revise:
        editor += [[("request_revision", {"feedback": "tighten the intro"})], [("check_draft", {})],
                   [("request_revision", {"feedback": "again"})], [("approve_draft", {})]]
        writer += [[("save_draft", {"markdown": DRAFT}), ("transfer_to_editor", {})]]
    else:
        editor += [[("approve_draft", {})]]
    return {
        "Admin": [[("transfer_to_researcher", {})], [("publish", {})]],
        "Researcher": [[("web_search", {"query": "how does a sundial work gnomon"})],
                       [("web_search", {"query": "sundial clock time equation"})],
                       [("transfer_to_planner", {})]],
        "Planner": [[("save_outline", {"title": "Reading Time From a Shadow",
                                       "sections": ["The gnomon (1, 2)", "Sun time vs clock time (3)"]})],
                    [("transfer_to_writer", {})]],
        "Writer": writer,
        "Editor": editor,
    }


def test_function_schema_hides_state_and_types_lists():
    def save_outline(title: str, sections: list[str], state: dict) -> str:
        """Save it."""
    fn = function_schema(save_outline)["function"]
    assert fn["description"] == "Save it."
    assert set(fn["parameters"]["properties"]) == {"title", "sections"}
    assert fn["parameters"]["properties"]["sections"] == {"type": "array", "items": {"type": "string"}}
    assert fn["parameters"]["required"] == ["title", "sections"]


def test_full_handoff_chain_produces_cited_post():
    search = CachedSearch.from_file(FIXTURE)
    llm = ScriptedLLM(happy_script())
    res = write_post("How sundials work", llm, word_budget=60, search=search)
    assert res.stopped == "done"
    handoffs = [(e["agent"], e["to"]) for e in res.log if e["event"] == "handoff"]
    assert handoffs == [("Admin", "Researcher"), ("Researcher", "Planner"), ("Planner", "Writer"),
                        ("Writer", "Editor"), ("Editor", "Admin")]
    post = res.state["final"]
    assert "## Sources" in post
    assert set(checks.parse_sources(post).values()) <= search.returned
    assert "kitchen.example.net" not in post
    assert all(checks.structure(post).values())
    assert llm.seen_tools[0] == ["transfer_to_researcher", "publish"]
    assert "save_draft" in llm.seen_tools[-3] or "check_draft" in llm.seen_tools[-3]


def test_editor_can_send_back_only_once():
    res = write_post("How sundials work", ScriptedLLM(happy_script(revise=True)), word_budget=60,
                     search=CachedSearch.from_file(FIXTURE))
    assert res.state["revisions"] == 1
    tool_results = [e["result"] for e in res.log if e["event"] == "tool" and e["tool"] == "request_revision"]
    assert tool_results[1].startswith("Revision limit reached")
    assert res.stopped == "done"


def test_save_draft_rejects_citations_that_are_not_search_results():
    script = happy_script()
    bad = DRAFT.replace("[3]", "[9]")
    script["Writer"] = [[("save_draft", {"markdown": bad})], [("save_draft", {"markdown": DRAFT}), ("transfer_to_editor", {})]]
    res = write_post("How sundials work", ScriptedLLM(script), word_budget=60, search=CachedSearch.from_file(FIXTURE))
    first = next(e for e in res.log if e.get("tool") == "save_draft")
    assert first["result"].startswith("Error: citations [9]")
    assert res.stopped == "done"


def test_handoff_guard_requires_sources_first():
    script = happy_script()
    script["Researcher"].insert(0, [("transfer_to_planner", {})])
    res = write_post("How sundials work", ScriptedLLM(script), word_budget=60, search=CachedSearch.from_file(FIXTURE))
    first = next(e for e in res.log if e.get("tool") == "transfer_to_planner")
    assert first["result"].startswith("Error: no sources")


def test_step_cap_stops_a_looping_agent():
    def ping() -> str:
        """Ping."""
        return "pong"

    class Loop:
        def chat(self, messages, tools=None):
            return {"content": "", "tool_calls": [{"id": "x", "name": "ping", "arguments": {}}], "reasoning": None}

    res = run(Loop(), Agent("Admin", "loop", [ping]), [{"role": "user", "content": "go"}], max_steps=5)
    assert res.stopped == "max_steps" and res.steps == 5
    assert sum(e["event"] == "tool" for e in res.log) == 5


def test_tool_errors_and_unknown_tools_go_back_to_the_model():
    def boom() -> str:
        """Boom."""
        raise RuntimeError("nope")

    class Two:
        n = 0

        def chat(self, messages, tools=None):
            self.n += 1
            if self.n == 1:
                return {"content": "", "tool_calls": [{"id": "a", "name": "boom", "arguments": {}},
                                                      {"id": "b", "name": "missing", "arguments": {}}], "reasoning": None}
            return {"content": "all done", "tool_calls": [], "reasoning": None}

    res = run(Two(), Agent("Admin", "x", [boom]), [{"role": "user", "content": "go"}])
    tool_msgs = [m["content"] for m in res.messages if m["role"] == "tool"]
    assert tool_msgs == ["Error: RuntimeError: nope", "Error: unknown tool missing"]
    assert res.stopped == "reply"


def test_handoff_result_switches_agent():
    b = Agent("B", "b", [])
    def go() -> Result:
        """Go."""
        return Result("bye", agent=b)

    class LLM:
        def chat(self, messages, tools=None):
            if messages[0]["content"].startswith("You are A"):
                return {"content": "", "tool_calls": [{"id": "1", "name": "go", "arguments": {}}], "reasoning": None}
            return {"content": "hi from B", "tool_calls": [], "reasoning": None}

    res = run(LLM(), Agent("A", "a", [go]), [{"role": "user", "content": "x"}])
    assert res.agent == "B"


def test_cached_search_is_deterministic_and_records_urls():
    s = CachedSearch.from_file(FIXTURE)
    a = s("gnomon latitude angle", 2)
    assert [h["url"] for h in a] == [h["url"] for h in s("gnomon latitude angle", 2)]
    assert a[0]["url"].endswith("/gnomon")
    assert s("zzz qqq", 3) == []
    assert s.returned == {h["url"] for h in a}


def test_html_to_text_drops_scripts_and_tags():
    assert html_to_text("<html><script>x=1</script><p>Hello&nbsp;<b>world</b></p></html>") == "Hello world"


def test_checks_on_a_good_and_a_bad_post():
    urls = {r["url"] for r in json.loads(FIXTURE.read_text())["search_results"]}
    good = DRAFT + "\n## Sources\n\n[1] a — https://timekeeping.example.org/sundials/basics\n" \
                   "[2] b — https://timekeeping.example.org/sundials/gnomon\n[3] c — https://clockwork.example.com/equation-of-time\n"
    assert all(checks.structure(good).values())
    assert citation_validity(good, urls) == 1.0
    bad = "Some text [4].\n\n## Sources\n\n[1] x — https://made-up.example.com/\n"
    assert citation_validity(bad, urls) == 0.0
    assert not checks.structure(bad)["title"]
    assert checks.word_count("# A b\n\nc d [1]\n\n## Sources\n\n[1] e — https://x.example.com") == 4


def test_budget_score():
    assert checks.budget_score(500, 500) == 1.0
    assert checks.budget_score(380, 500) == 1.0
    assert 0 < checks.budget_score(300, 500) < 1
    assert checks.budget_score(5000, 500) == 0.0


def test_scorer_on_practice_case():
    case = json.loads((ROOT / "eval/practice/bloom-filters.json").read_text())
    urls = {r["url"] for r in case["search_results"]}
    post = ("# Bloom\n\nIntro [1].\n\n## How\n\nA bit array and hash functions [1]. False positives but no false "
            "negatives [2].\n\n## History\n\nFrom 1970 [3].\n\n## Conclusion\n\nDone [1].\n\n## Sources\n\n"
            f"[1] a — {case['search_results'][0]['url']}\n[2] b — {case['search_results'][1]['url']}\n"
            f"[3] c — {case['search_results'][5]['url']}\n")
    assert fact_coverage(post, case["facts"]) == pytest.approx(3 / 5)
    r = score(post, case, urls)
    assert r["citations"] == 1.0 and r["structure"] == 1.0 and r["budget"] < 1.0
