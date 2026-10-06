import inspect
import json
import typing
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Agent:
    name: str
    instructions: str | Callable[[dict], str]
    tools: list[Callable] = field(default_factory=list)


@dataclass
class Result:
    value: str = ""
    agent: Agent | None = None
    done: bool = False


@dataclass
class RunResult:
    state: dict
    messages: list[dict]
    log: list[dict]
    agent: str
    steps: int
    stopped: str


_JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean", dict: "object"}


def _json_type(tp) -> dict:
    if typing.get_origin(tp) is list:
        (inner,) = typing.get_args(tp) or (str,)
        return {"type": "array", "items": _json_type(inner)}
    return {"type": _JSON_TYPES.get(tp, "string")}


def function_schema(fn: Callable) -> dict:
    hints = typing.get_type_hints(fn)
    props, required = {}, []
    for name, p in inspect.signature(fn).parameters.items():
        if name == "state":
            continue
        props[name] = _json_type(hints.get(name, str))
        if p.default is inspect.Parameter.empty:
            required.append(name)
    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": (inspect.getdoc(fn) or fn.__name__).strip(),
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }


def _summary(text: str, n: int = 160) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _call(fn: Callable, args: dict, state: dict) -> Any:
    params = inspect.signature(fn).parameters
    kwargs = {k: v for k, v in args.items() if k in params and k != "state"}
    if "state" in params:
        kwargs["state"] = state
    return fn(**kwargs)


def run(llm, agent: Agent, messages: list[dict], state: dict | None = None, max_steps: int = 30,
        on_event: Callable[[dict], None] | None = None) -> RunResult:
    state = state if state is not None else {}
    messages = list(messages)
    log: list[dict] = []

    def emit(event: dict) -> None:
        log.append(event)
        if on_event:
            on_event(event)

    nudged = False
    for step in range(1, max_steps + 1):
        instructions = agent.instructions(state) if callable(agent.instructions) else agent.instructions
        system = {"role": "system", "content": f"You are {agent.name}.\n\n{instructions}"}
        tools = {fn.__name__: fn for fn in agent.tools}
        reply = llm.chat([system] + messages, [function_schema(f) for f in agent.tools] or None)

        msg: dict = {"role": "assistant", "content": reply["content"] or ""}
        if reply.get("reasoning"):
            msg["reasoning_content"] = reply["reasoning"]
        if reply["tool_calls"]:
            msg["tool_calls"] = [
                {"id": c["id"], "type": "function",
                 "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])}}
                for c in reply["tool_calls"]
            ]
        messages.append(msg)

        if not reply["tool_calls"]:
            if not nudged and agent.name != "Admin":
                nudged = True
                emit({"step": step, "agent": agent.name, "event": "nudge", "text": _summary(reply["content"])})
                messages.append({"role": "user", "content": f"(runner) {agent.name}: finish your job by calling one of your tools."})
                continue
            emit({"step": step, "agent": agent.name, "event": "reply", "text": _summary(reply["content"])})
            return RunResult(state, messages, log, agent.name, step, "reply")

        next_agent, done = agent, False
        for call in reply["tool_calls"]:
            fn = tools.get(call["name"])
            if fn is None:
                out = Result(f"Error: unknown tool {call['name']}")
            else:
                try:
                    out = _call(fn, call["arguments"], state)
                except Exception as e:
                    out = Result(f"Error: {type(e).__name__}: {e}")
            if isinstance(out, Agent):
                out = Result(f"Handing off to {out.name}.", agent=out)
            if not isinstance(out, Result):
                out = Result(str(out))
            emit({"step": step, "agent": agent.name, "event": "tool", "tool": call["name"],
                  "args": {k: _summary(v, 80) for k, v in call["arguments"].items()},
                  "result": _summary(out.value)})
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": out.value})
            if out.agent is not None:
                emit({"step": step, "agent": agent.name, "event": "handoff", "to": out.agent.name})
                next_agent = out.agent
            done = done or out.done
        agent = next_agent
        if done:
            return RunResult(state, messages, log, agent.name, step, "done")

    emit({"step": max_steps, "agent": agent.name, "event": "max_steps"})
    return RunResult(state, messages, log, agent.name, max_steps, "max_steps")


def format_event(e: dict) -> str:
    if e["event"] == "tool":
        args = ", ".join(f"{k}={v!r}" for k, v in e["args"].items())
        return f"[{e['step']:02d}] {e['agent']:<10} {e['tool']}({args}) -> {e['result']}"
    if e["event"] == "handoff":
        return f"[{e['step']:02d}] {e['agent']:<10} ==> handoff to {e['to']}"
    if e["event"] in ("reply", "nudge"):
        return f"[{e['step']:02d}] {e['agent']:<10} {e['event']}: {e['text']}"
    return f"[{e['step']:02d}] {e['agent']:<10} stopped: hit the step cap"
