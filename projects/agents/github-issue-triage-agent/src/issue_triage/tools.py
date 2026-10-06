import json
from dataclasses import dataclass, field

from .snapshot import Snapshot

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "search_issues",
        "description": "BM25 keyword search over all issues in the repository (open and closed). "
                       "Returns the top matches with number, title, state, labels and score.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Keywords describing the problem or request"},
            "k": {"type": "integer", "description": "Max results (default 5)"},
        }, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "get_issue",
        "description": "Full title, body, author, date, state and labels of one issue.",
        "parameters": {"type": "object", "properties": {"number": {"type": "integer"}}, "required": ["number"]},
    }},
    {"type": "function", "function": {
        "name": "apply_label",
        "description": "Set the labels of the issue being triaged (replaces any labels you set before).",
        "parameters": {"type": "object", "properties": {
            "number": {"type": "integer"},
            "labels": {"type": "array", "items": {"type": "string"}},
        }, "required": ["number", "labels"]},
    }},
    {"type": "function", "function": {
        "name": "mark_duplicate",
        "description": "Mark the issue being triaged as a duplicate of an earlier issue.",
        "parameters": {"type": "object", "properties": {
            "number": {"type": "integer"},
            "of": {"type": "integer", "description": "The earlier issue it duplicates"},
        }, "required": ["number", "of"]},
    }},
    {"type": "function", "function": {
        "name": "draft_reply",
        "description": "Save a draft maintainer reply for the issue being triaged. It is never posted.",
        "parameters": {"type": "object", "properties": {
            "number": {"type": "integer"},
            "body": {"type": "string"},
        }, "required": ["number", "body"]},
    }},
]


@dataclass
class Workspace:

    snapshot: Snapshot
    target: int
    hide_own_labels: bool = True
    labels: list[str] = field(default_factory=list)
    duplicate_of: int | None = None
    reply: str = ""

    def call(self, name: str, args: dict) -> dict:
        fn = getattr(self, f"_t_{name}", None)
        if fn is None:
            return {"error": f"unknown tool {name!r}"}
        try:
            return fn(**args)
        except TypeError as e:
            return {"error": f"bad arguments for {name}: {e}"}

    def _check_target(self, number) -> dict | None:
        if int(number) != self.target:
            return {"error": f"you may only modify issue #{self.target}"}
        return None

    def _t_search_issues(self, query: str, k: int = 5) -> dict:
        hits = self.snapshot.index.search(query, k=min(int(k), 10), exclude={self.target})
        return {"results": [
            {"number": n, "title": self.snapshot.issues[n]["title"], "state": self.snapshot.issues[n]["state"],
             "labels": self.snapshot.issues[n]["labels"], "score": round(s, 2)} for n, s in hits]}

    def _t_get_issue(self, number) -> dict:
        issue = self.snapshot.issues.get(int(number))
        if issue is None:
            return {"error": f"issue #{number} not found"}
        issue = dict(issue)
        if issue["number"] == self.target and self.hide_own_labels:
            issue["labels"] = []
        return issue

    def _t_apply_label(self, number, labels) -> dict:
        if err := self._check_target(number):
            return err
        if isinstance(labels, str):
            labels = [labels]
        unknown = [lb for lb in labels if lb not in self.snapshot.label_set]
        if unknown:
            return {"error": f"unknown labels {unknown}; allowed: {self.snapshot.label_set}"}
        self.labels = sorted(set(labels))
        return {"ok": True, "labels": self.labels}

    def _t_mark_duplicate(self, number, of) -> dict:
        if err := self._check_target(number):
            return err
        if int(of) == self.target or int(of) not in self.snapshot.issues:
            return {"error": f"#{of} is not a valid issue to point to"}
        self.duplicate_of = int(of)
        return {"ok": True, "duplicate_of": self.duplicate_of}

    def _t_draft_reply(self, number, body: str) -> dict:
        if err := self._check_target(number):
            return err
        self.reply = body.strip()
        return {"ok": True, "saved_words": len(self.reply.split()), "note": "draft saved, not posted"}


def summarize_result(name: str, result: dict) -> str:
    if "error" in result:
        return f"error: {result['error']}"
    if name == "search_issues":
        hits = result["results"]
        return f"{len(hits)} hits: " + ", ".join(f"#{h['number']} ({h['score']})" for h in hits) if hits else "0 hits"
    if name == "get_issue":
        return f"#{result['number']} {result['title'][:60]!r}"
    if name == "apply_label":
        return "labels = " + ", ".join(result["labels"])
    if name == "mark_duplicate":
        return f"duplicate of #{result['duplicate_of']}"
    if name == "draft_reply":
        return f"draft saved ({result['saved_words']} words)"
    return json.dumps(result)[:80]
