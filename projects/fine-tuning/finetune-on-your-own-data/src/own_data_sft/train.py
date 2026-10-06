import json
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

IGNORE = -100


@dataclass
class TrainConfig:
    model: str = "HuggingFaceTB/SmolLM2-360M-Instruct"
    train_file: str = "data/processed/train.jsonl"
    val_file: str = "data/processed/val.jsonl"
    system: str = "You are the assistant for a small pottery studio. Answer briefly and only with facts you know."
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    target_modules: list[str] = field(default_factory=lambda: ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
    lr: float = 2e-4
    batch_size: int = 4
    epochs: int = 3
    max_len: int = 512
    seed: int = 0
    out_dir: str = "outputs/own-data"

    def validate(self) -> "TrainConfig":
        if min(self.lora_r, self.lora_alpha, self.batch_size, self.epochs, self.max_len) <= 0:
            raise ValueError("lora_r, lora_alpha, batch_size, epochs and max_len must be positive")
        if not 0 < self.lr < 1e-2:
            raise ValueError("lr out of range")
        return self


def load_rows(path: str | Path) -> list[list[dict]]:
    return [json.loads(l)["messages"] for l in Path(path).read_text().splitlines() if l.strip()]


def with_system(messages: list[dict], system: str | None) -> list[dict]:
    if not system or messages[0]["role"] == "system":
        return messages
    return [{"role": "system", "content": system}] + messages


def device() -> str:
    import torch

    return "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"


def encode(tok, messages: list[dict], max_len: int) -> tuple[list[int], list[int]] | None:
    def ids(text):
        return tok(text, add_special_tokens=False)["input_ids"]

    full = ids(tok.apply_chat_template(messages, tokenize=False))
    if len(full) > max_len:
        return None
    start = len(ids(tok.apply_chat_template(messages[:-1], tokenize=False, add_generation_prompt=True)))
    return full, [IGNORE] * start + full[start:]


def collate(rows, pad_id):
    import torch

    width = max(len(i) for i, _ in rows)
    ids = torch.full((len(rows), width), pad_id)
    lab = torch.full((len(rows), width), IGNORE)
    att = torch.zeros((len(rows), width), dtype=torch.long)
    for r, (i, l) in enumerate(rows):
        ids[r, : len(i)] = torch.tensor(i)
        lab[r, : len(l)] = torch.tensor(l)
        att[r, : len(i)] = 1
    return {"input_ids": ids, "labels": lab, "attention_mask": att}


def load_model(name: str, adapter: str | None = None):
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(name)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(name).to(device())
    if adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, adapter).to(device())
    return tok, model.eval()


def mean_loss(model, encoded, pad_id: int, batch_size: int = 8) -> float:
    import torch

    total, count = 0.0, 0
    with torch.no_grad():
        for i in range(0, len(encoded), batch_size):
            b = {k: v.to(model.device) for k, v in collate(encoded[i : i + batch_size], pad_id).items()}
            n = int((b["labels"][:, 1:] != IGNORE).sum())
            total += model(**b).loss.item() * n
            count += n
    return total / max(count, 1)


def generate(tok, model, question: str, system: str | None = None, max_new_tokens: int = 160) -> str:
    import torch

    msgs = with_system([{"role": "user", "content": question}], system)
    text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    enc = tok(text, return_tensors="pt", add_special_tokens=False).to(model.device)
    with torch.no_grad():
        out = model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=False, repetition_penalty=1.1,
                             pad_token_id=tok.pad_token_id)
    return tok.decode(out[0, enc["input_ids"].shape[1]:], skip_special_tokens=True).strip()


def train(cfg: TrainConfig) -> dict:
    import torch
    from peft import LoraConfig, get_peft_model

    cfg.validate()
    torch.manual_seed(cfg.seed)
    tok, model = load_model(cfg.model)
    train_ex = [e for m in load_rows(cfg.train_file) if (e := encode(tok, with_system(m, cfg.system), cfg.max_len))]
    val_ex = [e for m in load_rows(cfg.val_file) if (e := encode(tok, with_system(m, cfg.system), cfg.max_len))]
    val_before = mean_loss(model, val_ex, tok.pad_token_id)
    print(f"train {len(train_ex)}  val {len(val_ex)}  val loss before {val_before:.4f}")

    model = get_peft_model(model, LoraConfig(r=cfg.lora_r, lora_alpha=cfg.lora_alpha, lora_dropout=cfg.lora_dropout,
                                              target_modules=cfg.target_modules, task_type="CAUSAL_LM"))
    model.print_trainable_parameters()
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=cfg.lr)
    steps = cfg.epochs * max(1, len(train_ex) // cfg.batch_size)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / 5) * max(0.0, 1 - s / steps))
    rng = random.Random(cfg.seed)
    log, step, t0 = [], 0, time.time()
    model.train()
    for epoch in range(cfg.epochs):
        order = list(range(len(train_ex)))
        rng.shuffle(order)
        for i in range(0, len(order) - cfg.batch_size + 1, cfg.batch_size):
            b = {k: v.to(model.device) for k, v in collate([train_ex[j] for j in order[i : i + cfg.batch_size]], tok.pad_token_id).items()}
            loss = model(**b).loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            opt.zero_grad()
            step += 1
            log.append({"step": step, "epoch": epoch + 1, "loss": loss.item()})
        print(f"epoch {epoch + 1}  loss {log[-1]['loss']:.4f}  ({time.time() - t0:.0f}s)")

    model.eval()
    val_after = mean_loss(model, val_ex, tok.pad_token_id)
    print(f"val loss after {val_after:.4f}")
    out = Path(cfg.out_dir)
    model.save_pretrained(out / "adapter")
    tok.save_pretrained(out / "adapter")
    result = {"config": asdict(cfg), "steps": step, "device": device(), "train_seconds": round(time.time() - t0, 1),
              "val_loss_before": val_before, "val_loss_after": val_after, "log": log}
    (out / "result.json").write_text(json.dumps(result, indent=2))
    return result
