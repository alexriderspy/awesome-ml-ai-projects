from .data import parse_label, zero_shot_prompt
from .prices import PRICES, cost_usd

SYSTEM = "You are a support ticket router. Answer with exactly one category name from the list."


def classify_api(llm, text: str) -> dict:
    r = llm.chat(SYSTEM, zero_shot_prompt(text))
    cost = cost_usd(r.model, r.prompt_tokens, r.completion_tokens, r.cached_tokens) if r.model in PRICES else 0.0
    return {
        "pred": parse_label(r.text), "raw": r.text, "latency_s": r.latency_s, "cost_usd": cost,
        "prompt_tokens": r.prompt_tokens, "completion_tokens": r.completion_tokens, "cached_tokens": r.cached_tokens,
    }
