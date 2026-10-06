# Small Model Beats Big

Fine-tune a 360M model with LoRA to route support tickets into 8 categories, and compare it with a big API model and a TF-IDF baseline on accuracy, latency and cost.

Results so far on the 96-ticket test split ([`demo/comparison.md`](demo/comparison.md)):

| System | Accuracy | p50 latency | Cost / 1k tickets |
|---|---|---|---|
| TF-IDF + logistic regression | 0.875 | 1 ms | $0 |
| deepseek-flash zero-shot | 0.906 | 963 ms | $0.18 |
| SmolLM2-360M + LoRA | train it to fill this row | | $0 |

**Level:** Intermediate · **Time:** ~3 hours · **Runs on:** laptop CPU/MPS

## What you'll learn

- Turning classification into a short generation task for a small model
- LoRA fine-tuning with the loss on the answer only
- Comparing systems fairly: same test split, accuracy, macro-F1, latency, cost
- Why a cheap baseline belongs in every comparison

## How it works

```
800 synthetic tickets (data/generate.py) ─► stratified split: train / val / test
   ├─► TF-IDF + logistic regression
   ├─► SmolLM2-360M + LoRA (answers with the label name)
   └─► big API model, zero-shot with category descriptions
   ─► accuracy · macro-F1 · invalid answers · latency · cost
```

The tickets were generated once with an LLM for a made-up invoicing app and committed, so everyone tests on the same data.

## Milestones

- [ ] **1. Data** – generate, split, prompts (`data/generate.py`, `data.py`)
- [ ] **2. Baseline** – TF-IDF + logistic regression (`baseline.py`)
- [ ] **3. API model** – zero-shot router with token costs (`api_classifier.py`, `prices.py`)
- [ ] **4. Fine-tune** – LoRA on the small model (`local_model.py`)
- [ ] **5. Compare** – metrics, confusion matrices, table (`eval/run_eval.py`)

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env && export $(xargs < .env)

PYTHONPATH=src python -m ticket_router train
PYTHONPATH=src python -m ticket_router classify "I was charged twice this month"
```

## Score it

```bash
PYTHONPATH=src python eval/run_eval.py --systems tfidf,base,local,api
pytest -q tests
```

Score = test accuracy of the fine-tuned small model × 100. All systems are reported side by side.

## Leaderboard

| Builder | Model | Score |
|---|---|---|
| | | |

## Stretch goals

- Train on half the data and plot accuracy against training size
- Swap in a 1B model and see where the gains stop
- Distil: label more tickets with the big model, train the small one on them
