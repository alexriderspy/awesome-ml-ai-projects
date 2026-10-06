# Fine-tune Llama 3.2 3B

Supervised fine-tuning of Llama 3.2 3B with LoRA on FineTome-100k, plus the same pipeline in plain transformers + peft for a tiny model you can run on a laptop.

**Level:** Intermediate · **Time:** ~3 hours · **Runs on:** Colab T4 GPU (3B) or laptop CPU/MPS (135M)

Video: [Fine-tuning Llama 3.2 3B](https://www.youtube.com/watch?v=dn2anUU0d0U)

## What you'll learn

- Converting ShareGPT data into chat messages and a chat template
- Masking the loss so only assistant replies are trained
- LoRA and 4-bit loading with Unsloth
- Measuring the result: held-out loss and instruction-following checks

## How it works

```
FineTome-100k (ShareGPT) ─► chat messages ─► chat template ─► labels only on assistant tokens
   ─► LoRA SFT (Unsloth on GPU, or transformers + peft locally) ─► adapter
   ─► held-out loss + 20 instruction checks
```

## Milestones

- [ ] **1. Data** – ShareGPT to messages, validity checks (`data.py`)
- [ ] **2. Masking** – tokenize with labels only on replies (`data.py: tokenize_with_mask`)
- [ ] **3. Config** – one TOML per run, validated (`config.py`, `configs/`)
- [ ] **4. Train** – LoRA SFT loop with warmup and decay (`train.py`)
- [ ] **5. GPU run** – the 3B model in Colab (`gpu/finetune_llama_3_2_3b_unsloth.ipynb`)
- [ ] **6. Eval** – held-out loss and checks (`eval/run_eval.py`)

## Run it

On a GPU, open `gpu/finetune_llama_3_2_3b_unsloth.ipynb` in Colab and run all cells.

On a laptop, the same pipeline with a 135M model:

```bash
pip install -r requirements.txt

PYTHONPATH=src python -m finetome_sft show 2
PYTHONPATH=src python -m finetome_sft train --config configs/local-smollm2-135m.toml
PYTHONPATH=src python -m finetome_sft generate "Write a haiku about rain" --adapter outputs/local/adapter
```

## Score it

```bash
PYTHONPATH=src python eval/run_eval.py --config configs/local-smollm2-135m.toml --adapter outputs/local/adapter
pytest -q tests
```

| Part | Weight | Checks |
|---|---|---|
| Instruction checks | 100% | 20 original prompts with checkable rules (word limits, bullet counts, JSON keys, casing) |
| Held-out loss | reported | cross-entropy on FineTome rows never trained on |

## Leaderboard

| Builder | Model | Score |
|---|---|---|
| | | |

## Stretch goals

- Train for a full epoch and compare held-out loss
- Merge the adapter and export to GGUF for Ollama
- Compare LoRA ranks 8, 16 and 64
