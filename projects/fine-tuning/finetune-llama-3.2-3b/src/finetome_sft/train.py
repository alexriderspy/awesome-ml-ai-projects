import json
import math
import random
import time
from pathlib import Path

from .config import TrainConfig
from .data import collate, load_finetome, tokenize_with_mask


def device() -> str:
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def load_model(name: str, adapter: str | None = None):
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(name)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(name).to(device())
    if adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, adapter).to(device())
    model.eval()
    return tok, model


def mean_loss(model, examples, pad_id: int, batch_size: int = 8) -> float:
    import torch

    total, count = 0.0, 0
    with torch.no_grad():
        for i in range(0, len(examples), batch_size):
            b = {k: v.to(model.device) for k, v in collate(examples[i : i + batch_size], pad_id).items()}
            n = int((b["labels"][:, 1:] != -100).sum())
            total += model(**b).loss.item() * n
            count += n
    return total / max(count, 1)


def generate(tok, model, prompt: str, max_new_tokens: int = 200) -> str:
    import torch

    text = tok.apply_chat_template([{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True)
    ids = tok(text, return_tensors="pt", add_special_tokens=False).to(model.device)
    with torch.no_grad():
        out = model.generate(**ids, max_new_tokens=max_new_tokens, do_sample=False, repetition_penalty=1.1,
                             pad_token_id=tok.pad_token_id)
    return tok.decode(out[0, ids["input_ids"].shape[1]:], skip_special_tokens=True).strip()


def lr_at(step: int, cfg: TrainConfig) -> float:
    if step < cfg.warmup_steps:
        return cfg.lr * (step + 1) / cfg.warmup_steps
    return cfg.lr * max(0.0, (cfg.max_steps - step) / (cfg.max_steps - cfg.warmup_steps))


def train(cfg: TrainConfig, sample_prompts: list[str] | None = None) -> dict:
    import torch
    from peft import LoraConfig, get_peft_model

    torch.manual_seed(cfg.seed)
    out = Path(cfg.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    tok, model = load_model(cfg.model)
    train_convs, held_convs = load_finetome(cfg.n_rows, cfg.n_heldout, seed=cfg.seed)
    train_ex = [e for c in train_convs if (e := tokenize_with_mask(tok, c, cfg.max_len))]
    held_ex = [e for c in held_convs if (e := tokenize_with_mask(tok, c, cfg.max_len))]
    print(f"train examples {len(train_ex)} (of {len(train_convs)}), held-out {len(held_ex)} (of {len(held_convs)}), max_len {cfg.max_len}")

    before = {p: generate(tok, model, p) for p in (sample_prompts or [])}
    held_before = mean_loss(model, held_ex, tok.pad_token_id)
    print(f"held-out loss before: {held_before:.4f}")

    model = get_peft_model(model, LoraConfig(r=cfg.lora_r, lora_alpha=cfg.lora_alpha, lora_dropout=cfg.lora_dropout,
                                              target_modules=cfg.target_modules, task_type="CAUSAL_LM"))
    model.print_trainable_parameters()
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=cfg.lr, weight_decay=0.0)

    rng = random.Random(cfg.seed)
    order: list[int] = []
    log = []
    model.train()
    t0 = time.time()
    for step in range(cfg.max_steps):
        for g in opt.param_groups:
            g["lr"] = lr_at(step, cfg)
        step_loss = 0.0
        for _ in range(cfg.grad_accum):
            if len(order) < cfg.batch_size:
                order = list(range(len(train_ex)))
                rng.shuffle(order)
            batch = [train_ex[order.pop()] for _ in range(cfg.batch_size)]
            b = {k: v.to(model.device) for k, v in collate(batch, tok.pad_token_id).items()}
            loss = model(**b).loss / cfg.grad_accum
            loss.backward()
            step_loss += loss.item()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        opt.zero_grad()
        log.append({"step": step + 1, "loss": step_loss, "lr": lr_at(step, cfg)})
        if (step + 1) % 10 == 0 or step == 0:
            print(f"step {step + 1:4d}  loss {step_loss:.4f}  ({time.time() - t0:.0f}s)")

    model.eval()
    held_after = mean_loss(model, held_ex, tok.pad_token_id)
    print(f"held-out loss after:  {held_after:.4f}")
    after = {p: generate(tok, model, p) for p in (sample_prompts or [])}
    model.save_pretrained(out / "adapter")

    result = {
        "model": cfg.model, "steps": cfg.max_steps, "train_examples": len(train_ex), "heldout_examples": len(held_ex),
        "heldout_loss_before": held_before, "heldout_loss_after": held_after,
        "heldout_ppl_before": math.exp(held_before), "heldout_ppl_after": math.exp(held_after),
        "train_seconds": round(time.time() - t0, 1), "device": device(), "log": log,
        "samples": [{"prompt": p, "before": before[p], "after": after[p]} for p in before],
    }
    (out / "result.json").write_text(json.dumps(result, indent=2))
    return result


def plot_loss(log: list[dict], path: str | Path, title: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    steps = [r["step"] for r in log]
    loss = [r["loss"] for r in log]
    k = 5
    smooth = [sum(loss[max(0, i - k + 1): i + 1]) / len(loss[max(0, i - k + 1): i + 1]) for i in range(len(loss))]
    fig, ax = plt.subplots(figsize=(7, 3.6), dpi=120)
    ax.plot(steps, loss, color="#bbbbbb", lw=1, label="per step")
    ax.plot(steps, smooth, color="#111111", lw=2, label=f"{k}-step mean")
    ax.set_xlabel("optimizer step")
    ax.set_ylabel("train loss (assistant tokens)")
    ax.set_title(title, fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path)
