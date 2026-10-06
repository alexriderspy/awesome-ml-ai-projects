import json
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .data import parse_label, sft_messages, short_prompt

IGNORE = -100


@dataclass
class LocalConfig:
    model: str = "HuggingFaceTB/SmolLM2-360M-Instruct"
    lora_r: int = 16
    lora_alpha: int = 32
    target_modules: list[str] = field(default_factory=lambda: ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
    lr: float = 2e-4
    batch_size: int = 8
    epochs: int = 2
    max_len: int = 384
    seed: int = 0
    out_dir: str = "outputs/smollm2-360m-lora"

    def validate(self) -> "LocalConfig":
        if self.lora_r <= 0 or self.batch_size <= 0 or self.epochs <= 0 or self.max_len <= 0:
            raise ValueError("lora_r, batch_size, epochs and max_len must be positive")
        if not 0 < self.lr < 1e-2:
            raise ValueError("lr out of range")
        return self


def device() -> str:
    import torch

    return "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"


def encode(tok, messages: list[dict], max_len: int) -> tuple[list[int], list[int]]:
    def ids(text):
        return tok(text, add_special_tokens=False)["input_ids"]

    full = ids(tok.apply_chat_template(messages, tokenize=False))
    start = len(ids(tok.apply_chat_template(messages[:-1], tokenize=False, add_generation_prompt=True)))
    full = full[:max_len]
    labels = [IGNORE] * min(start, len(full)) + full[start:]
    return full, labels


def _batch(rows, pad_id):
    import torch

    w = max(len(i) for i, _ in rows)
    ids = torch.full((len(rows), w), pad_id)
    lab = torch.full((len(rows), w), IGNORE)
    att = torch.zeros((len(rows), w), dtype=torch.long)
    for r, (i, l) in enumerate(rows):
        ids[r, : len(i)] = torch.tensor(i)
        lab[r, : len(l)] = torch.tensor(l)
        att[r, : len(i)] = 1
    return {"input_ids": ids, "labels": lab, "attention_mask": att}


def load(model_name: str, adapter: str | None = None):
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(model_name)
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(model_name).to(device())
    if adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, adapter).to(device())
    return tok, model.eval()


def train(cfg: LocalConfig, train_rows: list[dict], val_rows: list[dict]) -> dict:
    import torch
    from peft import LoraConfig, get_peft_model

    cfg.validate()
    torch.manual_seed(cfg.seed)
    tok, model = load(cfg.model)
    model = get_peft_model(model, LoraConfig(r=cfg.lora_r, lora_alpha=cfg.lora_alpha, target_modules=cfg.target_modules,
                                              lora_dropout=0.05, task_type="CAUSAL_LM"))
    model.print_trainable_parameters()
    data = [encode(tok, sft_messages(r), cfg.max_len) for r in train_rows]
    steps = cfg.epochs * (len(data) // cfg.batch_size)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=cfg.lr)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / 10) * max(0.0, 1 - s / steps))
    rng = random.Random(cfg.seed)
    log, step, t0 = [], 0, time.time()
    model.train()
    for epoch in range(cfg.epochs):
        order = list(range(len(data)))
        rng.shuffle(order)
        for i in range(0, len(order) - cfg.batch_size + 1, cfg.batch_size):
            b = {k: v.to(model.device) for k, v in _batch([data[j] for j in order[i : i + cfg.batch_size]], tok.pad_token_id).items()}
            loss = model(**b).loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            opt.zero_grad()
            step += 1
            log.append({"step": step, "epoch": epoch + 1, "loss": loss.item()})
            if step % 10 == 0:
                print(f"epoch {epoch + 1} step {step}/{steps} loss {loss.item():.4f} ({time.time() - t0:.0f}s)")
    model.eval()
    val_preds = predict(tok, model, [r["text"] for r in val_rows])
    val_acc = sum(p["pred"] == r["label"] for p, r in zip(val_preds, val_rows)) / len(val_rows)
    print(f"val accuracy {val_acc:.3f}")
    out = Path(cfg.out_dir)
    model.save_pretrained(out / "adapter")
    result = {"config": asdict(cfg), "steps": step, "train_seconds": round(time.time() - t0, 1), "device": device(),
              "val_accuracy": val_acc, "log": log}
    (out / "train_result.json").write_text(json.dumps(result, indent=2))
    return result


def predict(tok, model, texts: list[str], batch_size: int = 1) -> list[dict]:
    import torch

    out = []
    for i in range(0, len(texts), batch_size):
        chunk = texts[i : i + batch_size]
        prompts = [tok.apply_chat_template([{"role": "user", "content": short_prompt(t)}], tokenize=False, add_generation_prompt=True) for t in chunk]
        enc = tok(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to(model.device)
        t0 = time.perf_counter()
        with torch.no_grad():
            gen = model.generate(**enc, max_new_tokens=8, do_sample=False, pad_token_id=tok.pad_token_id)
        if model.device.type == "mps":
            torch.mps.synchronize()
        dt = (time.perf_counter() - t0) / len(chunk)
        for row in gen[:, enc["input_ids"].shape[1]:]:
            raw = tok.decode(row, skip_special_tokens=True)
            out.append({"pred": parse_label(raw), "raw": raw, "latency_s": dt, "cost_usd": 0.0})
    return out
