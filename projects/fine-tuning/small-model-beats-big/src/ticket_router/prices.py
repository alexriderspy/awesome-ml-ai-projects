PRICES = {
    "deepseek-flash": {"input_miss": 0.30, "input_hit": 0.006, "output": 1.20},
    "deepseek-v4-pro": {"input_miss": 1.32, "input_hit": 0.044, "output": 3.96},
}


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0) -> float:
    p = PRICES[model]
    miss = prompt_tokens - cached_tokens
    return (miss * p["input_miss"] + cached_tokens * p["input_hit"] + completion_tokens * p["output"]) / 1e6
