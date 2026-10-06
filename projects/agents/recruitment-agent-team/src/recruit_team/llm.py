import json
import os
import threading
from typing import Any, Protocol

PRICES = {
    "deepseek-flash": {"input": 0.30, "output": 1.20},
    "deepseek-v4-pro": {"input": 1.32, "output": 3.96},
}


class ChatModel(Protocol):
    def complete(self, system: str, user: str) -> str: ...


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
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
        self._lock = threading.Lock()

    def _track(self, resp) -> None:
        u = getattr(resp, "usage", None)
        with self._lock:
            self.usage["calls"] += 1
            if u:
                self.usage["input_tokens"] += getattr(u, "prompt_tokens", 0) or 0
                self.usage["output_tokens"] += getattr(u, "completion_tokens", 0) or 0

    def cost_usd(self) -> float | None:
        p = PRICES.get(self.model)
        if not p:
            return None
        return (self.usage["input_tokens"] * p["input"] + self.usage["output_tokens"] * p["output"]) / 1e6

    def complete(self, system: str, user: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        self._track(resp)
        return resp.choices[0].message.content or ""

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        kwargs: dict[str, Any] = {"model": self.model, "temperature": self.temperature, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        resp = self.client.chat.completions.create(**kwargs)
        self._track(resp)
        msg = resp.choices[0].message
        calls = []
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {"_raw": tc.function.arguments}
            calls.append({"id": tc.id, "name": tc.function.name, "arguments": args})
        return {"content": msg.content or "", "tool_calls": calls}


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
