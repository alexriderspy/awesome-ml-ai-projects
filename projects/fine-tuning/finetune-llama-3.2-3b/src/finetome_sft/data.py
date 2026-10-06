from dataclasses import dataclass

ROLE_MAP = {"human": "user", "user": "user", "gpt": "assistant", "assistant": "assistant", "system": "system"}
IGNORE = -100


def sharegpt_to_messages(conversations: list[dict]) -> list[dict]:
    out = []
    for turn in conversations:
        role = ROLE_MAP.get(turn.get("from", "").lower())
        if role is None:
            raise ValueError(f"unknown ShareGPT role: {turn.get('from')!r}")
        out.append({"role": role, "content": turn.get("value", "").strip()})
    return out


def is_valid(messages: list[dict]) -> bool:
    turns = [m for m in messages if m["role"] != "system"]
    if not turns or turns[-1]["role"] != "assistant" or any(not m["content"] for m in messages):
        return False
    return all(m["role"] == ("user" if i % 2 == 0 else "assistant") for i, m in enumerate(turns))


@dataclass
class Example:
    input_ids: list[int]
    labels: list[int]


def _ids(tok, text: str) -> list[int]:
    return tok(text, add_special_tokens=False)["input_ids"]


def tokenize_with_mask(tok, messages: list[dict], max_len: int) -> Example | None:
    full = _ids(tok, tok.apply_chat_template(messages, tokenize=False))
    labels = [IGNORE] * len(full)
    for i, m in enumerate(messages):
        if m["role"] != "assistant":
            continue
        start = len(_ids(tok, tok.apply_chat_template(messages[:i], tokenize=False, add_generation_prompt=True)))
        end = len(_ids(tok, tok.apply_chat_template(messages[: i + 1], tokenize=False)))
        labels[start:end] = full[start:end]
    if len(full) > max_len:
        return None
    if all(x == IGNORE for x in labels):
        return None
    return Example(full, labels)


def collate(batch: list[Example], pad_id: int) -> dict:
    import torch

    width = max(len(e.input_ids) for e in batch)
    ids = torch.full((len(batch), width), pad_id, dtype=torch.long)
    lab = torch.full((len(batch), width), IGNORE, dtype=torch.long)
    att = torch.zeros((len(batch), width), dtype=torch.long)
    for r, e in enumerate(batch):
        n = len(e.input_ids)
        ids[r, :n] = torch.tensor(e.input_ids)
        lab[r, :n] = torch.tensor(e.labels)
        att[r, :n] = 1
    return {"input_ids": ids, "labels": lab, "attention_mask": att}


def load_finetome(n_rows: int, n_heldout: int, seed: int = 0) -> tuple[list[list[dict]], list[list[dict]]]:
    import random

    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download

    path = hf_hub_download("mlabonne/FineTome-100k", "data/train-00000-of-00001.parquet", repo_type="dataset")
    pf = pq.ParquetFile(path)
    convs = []
    for batch in pf.iter_batches(batch_size=1000, columns=["conversations"]):
        for conv in batch.column(0).to_pylist():
            msgs = sharegpt_to_messages(conv)
            if is_valid(msgs):
                convs.append(msgs)
        if len(convs) >= n_rows:
            break
    convs = convs[:n_rows]
    random.Random(seed).shuffle(convs)
    return convs[n_heldout:], convs[:n_heldout]
