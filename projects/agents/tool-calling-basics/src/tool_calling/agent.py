import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Protocol

from .schema import Tool, check_args

SYSTEM = (
    "You are a careful assistant with tools. Use the calculator for any arithmetic and unit_convert for "
    "any unit conversion instead of doing them in your head. Use get_weather for current weather and the "
    "notes tools for the user's notes. When you need several independent lookups, request all of those "
    "tool calls in the same turn. If a tool returns an error, fix the arguments and retry, or explain the "
    "problem to the user. Answer briefly and quote the numbers the tools returned."
)


class ToolChatModel(Protocol):
    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict: ...


@dataclass
class TraceEntry:
    step: int
    tool: str
    args: dict
    result: str
    ok: bool
    call_id: str
    batch_size: int


@dataclass
class AgentResult:
    answer: str
    trace: list[TraceEntry] = field(default_factory=list)
    steps: int = 0
    stopped: bool = False
    messages: list[dict] = field(default_factory=list)


def run_tool(call: dict, tools: dict[str, Tool]) -> tuple[str, bool]:
    name, args = call["name"], call["arguments"]
    if name not in tools:
        return f"Error: unknown tool '{name}'. Available tools: {', '.join(tools)}", False
    if "_raw" in args:
        return f"Error: arguments were not valid JSON: {args['_raw']!r}", False
    problem = check_args(args, tools[name].schema["function"]["parameters"])
    if problem:
        return f"Error: {problem}", False
    try:
        result = tools[name](**args)
    except Exception as e:
        return f"Error: {name} failed: {type(e).__name__}: {e}", False
    return (result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)), True


def run_agent(question: str, llm: ToolChatModel, tools: list[Tool], max_steps: int = 6,
              system: str = SYSTEM, history: list[dict] | None = None, log=None) -> AgentResult:
    by_name = {t.name: t for t in tools}
    schemas = [t.schema for t in tools]
    messages = [{"role": "system", "content": system}, *(history or []), {"role": "user", "content": question}]
    result = AgentResult(answer="", messages=messages)

    for step in range(1, max_steps + 1):
        reply = llm.chat(messages, tools=schemas)
        result.steps = step
        calls = reply["tool_calls"]
        if not calls:
            result.answer = reply["content"].strip()
            messages.append({"role": "assistant", "content": reply["content"]})
            return result

        assistant = {
            "role": "assistant",
            "content": reply["content"] or None,
            "tool_calls": [{"id": c["id"], "type": "function",
                            "function": {"name": c["name"], "arguments": c.get("raw_arguments") or json.dumps(c["arguments"])}}
                           for c in calls],
        }
        if reply.get("reasoning_content"):
            assistant["reasoning_content"] = reply["reasoning_content"]
        messages.append(assistant)

        with ThreadPoolExecutor(max_workers=min(8, len(calls))) as pool:
            outputs = list(pool.map(lambda c: run_tool(c, by_name), calls))

        for call, (output, ok) in zip(calls, outputs):
            entry = TraceEntry(step, call["name"], call["arguments"], output, ok, call["id"], len(calls))
            result.trace.append(entry)
            if log:
                log(entry)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": output})

    result.stopped = True
    result.answer = f"Stopped after {max_steps} steps without a final answer."
    return result


def format_entry(e: TraceEntry, width: int = 160) -> str:
    tag = f"step {e.step}" + (f" (parallel x{e.batch_size})" if e.batch_size > 1 else "")
    args = json.dumps(e.args, ensure_ascii=False)
    res = e.result if len(e.result) <= width else e.result[:width] + "..."
    return f"[{tag}] {e.tool}({args}) -> {'' if e.ok else '!! '}{res}"
