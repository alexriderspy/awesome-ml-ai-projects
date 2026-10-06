DATASET = "unsloth/LaTeX_OCR"
INSTRUCTION = "Write the LaTeX representation for this image."


def to_conversation(sample: dict) -> dict:
    return {"messages": [
        {"role": "user", "content": [{"type": "text", "text": INSTRUCTION}, {"type": "image", "image": sample["image"]}]},
        {"role": "assistant", "content": [{"type": "text", "text": sample["text"]}]},
    ]}


def prompt_messages() -> list[dict]:
    return [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": INSTRUCTION}]}]


def load_split(split: str = "test", limit: int | None = None, seed: int = 0):
    from datasets import load_dataset

    ds = load_dataset(DATASET, split=split)
    if limit:
        ds = ds.shuffle(seed=seed).select(range(min(limit, len(ds))))
    return ds
