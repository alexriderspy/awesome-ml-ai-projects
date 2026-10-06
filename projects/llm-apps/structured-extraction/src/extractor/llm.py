import os
import re
from typing import Protocol


class ChatModel(Protocol):
    def complete(self, system: str, user: str) -> str: ...


_LEAK = re.compile(r"<ds_safety>.*?</ds_safety>", re.S)


def clean(text: str) -> str:
    text = _LEAK.sub("", text)
    cut = text.find("<ds_safety>")
    return text[:cut] if cut != -1 else text


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
        self.calls = 0
        self.tokens = 0

    def chat(self, messages: list[dict], temperature: float | None = None) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature if temperature is None else temperature,
            messages=messages,
        )
        self.calls += 1
        if resp.usage:
            self.tokens += resp.usage.total_tokens or 0
        return clean(resp.choices[0].message.content or "")

    def complete(self, system: str, user: str) -> str:
        return self.chat([{"role": "system", "content": system}, {"role": "user", "content": user}])
