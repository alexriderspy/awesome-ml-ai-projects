import json
from dataclasses import dataclass, field
from typing import Callable

from .llm import ChatModel
from .sandbox import Sandbox
from .tools import SCHEMAS, Toolbox

SYSTEM = """You are a careful software engineer fixing a bug in a small Python repository.
Tools: list_files, read_file, write_file (full file content), run_tests (pytest).
Rules:
- Never edit tests or test config; they define correct behaviour. Fix the source code.
- Start by listing files and reading the failing tests and the code they import.
- Make the smallest change that fixes the issue. Write the whole file when you edit it.
- Run the tests after every edit. When they all pass, reply with a one-line summary and no tool call."""


@dataclass
class AgentResult:
    steps: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    trace: list[dict] = field(default_factory=list)
    final_message: str = ""
    stopped: str = ""

    @property
    def tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


def _estimate_tokens(obj) -> int:
    return max(1, len(json.dumps(obj, default=str)) // 4)


def _summary(text: str, n: int = 160) -> str:
    one = " ".join(text.split())
    return one if len(one) <= n else one[:n] + "..."


def run_agent(llm: ChatModel, sandbox: Sandbox, issue: str, max_steps: int = 20,
              on_event: Callable[[dict], None] | None = None) -> AgentResult:
    tools = Toolbox(sandbox)
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Issue:\n{issue}\n\nThe tests in this repository fail. Fix the code."}]
    res = AgentResult()
    emit = on_event or (lambda e: None)

    while res.steps < max_steps:
        res.steps += 1
        reply = llm.chat(messages, SCHEMAS)
        usage = reply.get("usage") or {}
        if usage.get("prompt_tokens") or usage.get("completion_tokens"):
            res.prompt_tokens += usage.get("prompt_tokens", 0)
            res.completion_tokens += usage.get("completion_tokens", 0)
        else:
            res.prompt_tokens += _estimate_tokens(messages)
            res.completion_tokens += _estimate_tokens(reply.get("message") or reply.get("content", ""))

        messages.append(reply.get("message") or {"role": "assistant", "content": reply.get("content", "")})
        if reply.get("content"):
            emit({"type": "thought", "step": res.steps, "text": reply["content"]})

        if not reply["tool_calls"]:
            res.final_message = reply.get("content", "")
            res.stopped = "done"
            return res

        for call in reply["tool_calls"]:
            out = tools.call(call["name"], call["arguments"])
            entry = {"step": res.steps, "tool": call["name"], "args": call["arguments"], "result": _summary(out)}
            res.trace.append(entry)
            emit({"type": "tool", **entry, "full_result": out})
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": out})

    res.stopped = "step_cap"
    return res
