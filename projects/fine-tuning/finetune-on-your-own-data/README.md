# Fine-tune on Your Own Data

Turn your own notes, chat exports and FAQ into a clean instruction dataset, then fine-tune a model on it with LoRA. The example data is an original pottery studio's FAQ, notes and WhatsApp-style chats.

**Level:** Intermediate · **Time:** ~3 hours · **Runs on:** laptop CPU/MPS (360M) or Colab T4 GPU (Llama 3.2 3B)

Video: [Fine-tuning on a personal dataset](https://www.youtube.com/watch?v=OxfeK423y2I)

## What you'll learn

- Turning raw text into instruction/response pairs
- Cleaning: PII scrubbing, length filters, exact and near-duplicate removal
- A stable train/val split that doesn't reshuffle when you add data
- LoRA fine-tuning on a small dataset, and checking it learned your facts

The video used Llama 2 7B. Smaller current models (SmolLM2, Llama 3.2) follow instructions better and train on a laptop or a free GPU, so this version uses them.

## How it works

```
faq.csv · notes.md · chats.txt ─► pairs ─► scrub PII ─► length filter ─► dedupe ─► train/val
   ─► LoRA SFT ─► adapter ─► answer val questions ─► score against the real answers
```

## Milestones

- [ ] **1. Ingest** – FAQ, notes and chat exports to pairs (`prepare.py`)
- [ ] **2. Clean** – PII scrub, filters, dedupe, report of what was dropped (`prepare.py`)
- [ ] **3. Split** – hash-based train/val split (`prepare.py`)
- [ ] **4. Train** – LoRA SFT with loss on replies only (`train.py`)
- [ ] **5. GPU run** – Llama 3.2 3B in Colab (`gpu/finetune_own_data_unsloth.ipynb`)
- [ ] **6. Eval** – val loss and answer overlap (`eval/run_eval.py`)

## Run it

```bash
pip install -r requirements.txt

PYTHONPATH=src python -m own_data_sft prepare
PYTHONPATH=src python -m own_data_sft train
PYTHONPATH=src python -m own_data_sft chat "How much is the beginner wheel course?"
```

To use your own data, replace the files in `data/raw/` and set `--owner` to your name in the chat export.

## Score it

```bash
PYTHONPATH=src python eval/run_eval.py --adapter outputs/own-data/adapter
PYTHONPATH=src python eval/run_eval.py                                     # base model, for comparison
pytest -q tests
```

| Part | Weight | Checks |
|---|---|---|
| Answer overlap | 70% | token F1 against the real answer, per val question |
| Numbers | 30% | prices, times and quantities from the real answer appear |
| Val loss | reported | cross-entropy on replies the model never trained on |

## Leaderboard

| Builder | Model | Score |
|---|---|---|
| | | |

## Stretch goals

- Add a refusal set: questions the data can't answer
- Compare fine-tuning with RAG over the same data
- Generate extra paraphrased questions to grow the dataset
