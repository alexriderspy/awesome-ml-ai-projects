import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from issue_triage import Snapshot, cost_usd, triage
from issue_triage.llm import Reply, ToolCall
from issue_triage.tools import Workspace
from run_eval import dup_scores, efficiency, label_scores, load_gold, reply_score, score_run


@pytest.fixture(scope="module")
def snap():
    return Snapshot.load()


class ScriptedLLM:

    def __init__(self, turns):
        self.turns, self.seen = list(turns), []

    def chat(self, messages, tools=None):
        self.seen.append(messages)
        if not self.turns:
            return Reply("Done.", [], 100, 10)
        calls = [ToolCall(f"c{i}", name, json.dumps(args)) for i, (name, args) in enumerate(self.turns.pop(0))]
        return Reply("", calls, 100, 10)


def test_snapshot_shape(snap):
    assert len(snap.issues) == 60
    assert snap.untriaged() == list(range(36, 61))
    assert all(set(i["labels"]) <= set(snap.label_set) for i in snap.issues.values())


def test_gold_is_separate_and_complete(snap):
    gold = load_gold()
    assert set(gold["labels"]) == set(snap.issues)
    assert len(gold["dupes"]) == 12
    for dup, orig in gold["dupes"].items():
        assert orig < dup
        assert snap.issues[dup]["title"] != snap.issues[orig]["title"]
    assert all(not snap.issues[n]["labels"] for n in gold["dupes"])


def test_bm25_ranks_relevant_issue(snap):
    hits = snap.index.search("draft posts appear in rss feed", k=3)
    assert {17, 52} & {n for n, _ in hits}
    assert snap.index.search("zzzz qqqq") == []


def test_workspace_writes_only_target(snap):
    ws = Workspace(snap, 37)
    assert "error" in ws.call("apply_label", {"number": 8, "labels": ["bug"]})
    assert "error" in ws.call("apply_label", {"number": 37, "labels": ["urgent"]})
    assert ws.call("apply_label", {"number": 37, "labels": ["bug", "bug"]})["labels"] == ["bug"]
    assert "error" in ws.call("mark_duplicate", {"number": 37, "of": 37})
    assert "error" in ws.call("nope", {})
    assert "error" in ws.call("get_issue", {"wrong": 1})
    assert 37 not in [r["number"] for r in ws.call("search_issues", {"query": "stylesheet restart"})["results"]]


def test_own_labels_hidden(snap):
    assert Workspace(snap, 8).call("get_issue", {"number": 8})["labels"] == []
    assert Workspace(snap, 37).call("get_issue", {"number": 8})["labels"] == ["bug"]


def test_agent_loop_records_actions_trace_and_tokens(snap):
    llm = ScriptedLLM([
        [("get_issue", {"number": 37})],
        [("search_issues", {"query": "css live reload"})],
        [("apply_label", {"number": 37, "labels": ["bug"]}), ("mark_duplicate", {"number": 37, "of": 8})],
        [("draft_reply", {"number": 37, "body": "Thanks! This is the same as #8, closing as duplicate."})],
    ])
    r = triage(37, snap, llm)
    assert r.labels == ["bug"] and r.duplicate_of == 8 and "#8" in r.reply
    assert [t["tool"] for t in r.trace] == ["get_issue", "search_issues", "apply_label", "mark_duplicate", "draft_reply"]
    assert r.steps == 5 and r.stopped == "done" and r.final == "Done."
    assert (r.prompt_tokens, r.completion_tokens) == (500, 50)
    msgs = llm.seen[-1]
    assert [m["role"] for m in msgs[-3:]] == ["assistant", "tool", "assistant"]
    assert msgs[-3]["tool_calls"][0]["id"] == msgs[-2]["tool_call_id"]


def test_step_cap(snap):
    llm = ScriptedLLM([[("search_issues", {"query": "x"})]] * 50)
    r = triage(40, snap, llm, max_steps=3)
    assert r.stopped == "step_cap" and r.steps == 3


def test_bad_json_arguments_do_not_crash(snap):
    class Bad:
        n = 0

        def chat(self, messages, tools=None):
            self.n += 1
            if self.n == 1:
                return Reply("", [ToolCall("x", "get_issue", "{not json")])
            return Reply("ok")

    r = triage(40, snap, Bad())
    assert r.trace[0]["result"].startswith("error")


def test_label_scores():
    s = label_scores({1: {"bug"}, 2: {"feature", "docs"}}, {1: {"bug"}, 2: {"feature"}})
    assert s["precision"] == pytest.approx(2 / 3) and s["recall"] == 1.0 and s["exact"] == 0.5


def test_dup_scores_unordered_and_recall_scope():
    gold = {46: 39, 37: 8}
    s = dup_scores({39: 46, 41: None}, gold)
    assert s["precision"] == 1.0 and s["recall"] == 1.0
    s = dup_scores({37: 41}, gold)
    assert s["precision"] == 0.0 and s["recall"] == 0.0
    assert dup_scores({41: None}, gold)["f1"] == 1.0


def test_reply_score():
    long = "thanks for the report we will look into this soon "
    assert reply_score("", {"bug"}, None) == 0.0
    assert reply_score(long + "see #8", {"bug"}, 8) == 1.0
    assert reply_score(long, {"bug"}, 8) == 0.0
    assert reply_score(long + "which version and steps?", {"bug", "needs-repro"}, None) == 1.0


def test_efficiency_and_cost():
    assert efficiency(10_000) == 1.0 and efficiency(60_000) == 0.0
    assert efficiency(37_500) == pytest.approx(0.5)
    assert cost_usd(1_000_000, 1_000_000, 0.28, 0.42) == pytest.approx(0.70)


def test_score_run_perfect():
    gold = load_gold()
    results = [{"number": n, "labels": sorted(gold["labels"][n]), "duplicate_of": gold["dupes"].get(n),
                "reply": f"thanks for filing this, please share version and steps; see #{gold['dupes'].get(n, 0)}",
                "prompt_tokens": 9000, "completion_tokens": 500} for n in range(36, 61)]
    assert score_run(results, gold)["overall"] == 100.0
