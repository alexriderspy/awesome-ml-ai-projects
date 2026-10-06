import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path


@dataclass
class TrainConfig:
    model: str = "HuggingFaceTB/SmolLM2-135M-Instruct"
    n_rows: int = 2000
    n_heldout: int = 100
    max_len: int = 512
    lora_r: int = 16
    lora_alpha: int = 16
    lora_dropout: float = 0.0
    target_modules: list[str] = field(default_factory=lambda: ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
    load_in_4bit: bool = False
    lr: float = 2e-4
    batch_size: int = 4
    grad_accum: int = 2
    max_steps: int = 60
    warmup_steps: int = 5
    seed: int = 3407
    out_dir: str = "outputs/local"

    def validate(self) -> "TrainConfig":
        errs = []
        if self.n_heldout >= self.n_rows:
            errs.append("n_heldout must be smaller than n_rows")
        if self.lora_r <= 0 or self.lora_alpha <= 0:
            errs.append("lora_r and lora_alpha must be positive")
        if not 0 <= self.lora_dropout < 1:
            errs.append("lora_dropout must be in [0, 1)")
        if not 0 < self.lr < 1e-2:
            errs.append("lr looks wrong (expected 0 < lr < 1e-2)")
        if min(self.batch_size, self.grad_accum, self.max_steps, self.max_len) <= 0:
            errs.append("batch_size, grad_accum, max_steps and max_len must be positive")
        if self.warmup_steps >= self.max_steps:
            errs.append("warmup_steps must be smaller than max_steps")
        if not self.target_modules:
            errs.append("target_modules is empty")
        if errs:
            raise ValueError("; ".join(errs))
        return self


def load_config(path: str | Path) -> TrainConfig:
    raw = tomllib.loads(Path(path).read_text())
    known = {f.name for f in fields(TrainConfig)}
    unknown = set(raw) - known
    if unknown:
        raise ValueError(f"unknown config keys: {sorted(unknown)}")
    return TrainConfig(**raw).validate()
