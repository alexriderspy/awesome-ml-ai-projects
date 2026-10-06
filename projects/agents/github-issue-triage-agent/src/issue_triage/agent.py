import json
import time
from dataclasses import asdict, dataclass, field

from .snapshot import Snapshot
from .tools import TOOL_SCHEMAS, Workspace, summarize_result

SYSTEM = """You are a maintainer triaging new GitHub issues for {project}, a small open-source static site \
generator CLI (`tinsel build`, `tinsel serve --watch`, `tinsel new post`, `tinsel check-links`, config in tinsel.toml).

Labels (use only these):
- bug: tinsel does something wrong (crash, wrong output, regression), including "it is slow" reports about existing behavior
- feature: a request for new behavior, option, command or optimization
- docs: documentation is missing, wrong or outdated (not a question about how to do something)
- question: the user asks how to do something; nothing is claimed to be broken
- performance: add to bug/feature when the issue is about speed or memory
- needs-repro: add to bug when the report has no steps, version or details to reproduce it
- good-first-issue: add when the fix is small and well scoped (a typo, a missing doc line, a simple flag)
Pick exactly one of bug/feature/docs/question, then any modifiers that apply.

Procedure:
1. get_issue on the issue you are triaging.
2. search_issues with 1-3 different keyword queries to look for an earlier issue about the SAME problem or request.
   Use get_issue on a promising hit if the title alone is not enough. Look at earlier labels for consistency.
3. apply_label.
4. If an earlier issue (lower number) reports the same underlying problem or asks for the same thing, even in
   different words, call mark_duplicate pointing to it. Same area but a different problem is NOT a duplicate.
5. draft_reply: a short, friendly maintainer reply (under 100 words). If duplicate, mention the earlier issue as #N.
   If needs-repro, ask for the tinsel version, OS and exact steps to reproduce. Never promise dates.
6. Finish with one plain sentence summarizing what you did (no tool call).
Only modify issue #{target}."""


@dataclass
class TriageResult:
    number: int
    labels: list[str]
    duplicate_of: int | None
    reply: str
    trace: list[dict] = field(default_factory=list)
    steps: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    final: str = ""
    stopped: str = "done"

    def to_dict(self) -> dict:
        return asdict(self)


def triage(number: int, snapshot: Snapshot, llm, max_steps: int = 10, on_event=None) -> TriageResult:
    if number not in snapshot.issues:
        raise ValueError(f"issue #{number} is not in the snapshot")
    ws = Workspace(snapshot, number)
    messages = [
        {"role": "system", "content": SYSTEM.format(project=snapshot.project, target=number)},
        {"role": "user", "content": f"Triage issue #{number}."},
    ]
    res = TriageResult(number, [], None, "")
    t0 = time.time()
    for step in range(1, max_steps + 1):
        reply = llm.chat(messages, TOOL_SCHEMAS)
        res.steps = step
        res.prompt_tokens += reply.prompt_tokens
        res.completion_tokens += reply.completion_tokens
        messages.append(reply.as_message())
        if not reply.tool_calls:
            res.final = reply.content.strip()
            break
        for call in reply.tool_calls:
            try:
                args = json.loads(call.arguments or "{}")
            except json.JSONDecodeError:
                args, result = {}, {"error": "arguments were not valid JSON"}
            else:
                result = ws.call(call.name, args) if isinstance(args, dict) else {"error": "arguments must be an object"}
            entry = {"step": step, "tool": call.name, "args": args, "result": summarize_result(call.name, result)}
            res.trace.append(entry)
            if on_event:
                on_event(entry)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result, ensure_ascii=False)})
    else:
        res.stopped = "step_cap"
    res.labels, res.duplicate_of, res.reply = ws.labels, ws.duplicate_of, ws.reply
    res.seconds = round(time.time() - t0, 1)
    return res


def cost_usd(prompt_tokens: int, completion_tokens: int, price_in: float, price_out: float) -> float:
    return (prompt_tokens * price_in + completion_tokens * price_out) / 1e6
