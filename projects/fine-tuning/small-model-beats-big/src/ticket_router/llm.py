import os
import time
from dataclasses import dataclass
from typing import Protocol


@dataclass
class Reply:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    latency_s: float = 0.0
    model: str = ""


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
            max_retries=3,
        )

    def chat(self, system: str, user: str, **kwargs) -> Reply:
        t0 = time.perf_counter()
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            **kwargs,
        )
        u = resp.usage
        cached = getattr(u, "prompt_cache_hit_tokens", None)
        if cached is None and getattr(u, "prompt_tokens_details", None) is not None:
            cached = u.prompt_tokens_details.cached_tokens
        return Reply(
            text=resp.choices[0].message.content or "",
            prompt_tokens=u.prompt_tokens if u else 0,
            completion_tokens=u.completion_tokens if u else 0,
            cached_tokens=cached or 0,
            latency_s=time.perf_counter() - t0,
            model=self.model,
        )

    def complete(self, system: str, user: str) -> str:
        return self.chat(system, user).text
