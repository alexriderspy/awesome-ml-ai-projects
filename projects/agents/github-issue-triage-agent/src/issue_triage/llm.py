import json
import os
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class Reply:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def as_message(self) -> dict:
        msg: dict[str, Any] = {"role": "assistant", "content": self.content or ""}
        if self.tool_calls:
            msg["tool_calls"] = [
                {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
                for c in self.tool_calls
            ]
        return msg


class ChatModel(Protocol):
    def complete(self, system: str, user: str) -> str: ...
    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> Reply: ...


class OpenAICompatible:
    def __init__(self, model: str | None = None, base_url: str | None = None, api_key: str | None = None,
                 temperature: float = 0.2):
        from openai import OpenAI

        self.model = model or os.getenv("LLM_MODEL", "llama3.2")
        self.temperature = temperature
        self.client = OpenAI(
            base_url=base_url or os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
            api_key=api_key or os.getenv("LLM_API_KEY", "ollama"),
        )

    def complete(self, system: str, user: str) -> str:
        return self.chat([{"role": "system", "content": system}, {"role": "user", "content": user}]).content

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> Reply:
        kwargs: dict[str, Any] = {"model": self.model, "temperature": self.temperature, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        resp = self.client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        calls = [ToolCall(c.id, c.function.name, c.function.arguments or "{}") for c in (msg.tool_calls or [])]
        usage = resp.usage
        return Reply(
            content=msg.content or "",
            tool_calls=calls,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )


def parse_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    pairs = sorted((("{", "}"), ("[", "]")), key=lambda p: text.find(p[0]) % (len(text) + 1))
    for open_ch, close_ch in pairs:
        start, end = text.find(open_ch), text.rfind(close_ch)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"No JSON found in model reply: {text[:200]!r}")
