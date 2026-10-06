# Fine-tune Qwen2-VL for LaTeX OCR

Teach a vision-language model to read an image of a formula and write its LaTeX. Fine-tuned with Unsloth on the LaTeX_OCR dataset.

**Level:** Advanced · **Time:** ~3 hours · **Runs on:** Colab T4 GPU (2B) or L4/A100 (7B)

Video: [Fine-tuning Qwen2-VL on LaTeX images](https://www.youtube.com/watch?v=i5kDh35sJ9M)

## What you'll learn

- Chat-format data with images for a vision-language model
- LoRA on both the vision and language layers with Unsloth
- Scoring OCR output: exact match, edit distance and BLEU
- Normalising LaTeX so spacing differences don't count as errors

## How it works

```
LaTeX_OCR (image, latex) ─► chat: [image + instruction] → latex
   ─► Qwen2-VL + LoRA (4-bit, Unsloth) ─► adapter
   ─► transcribe the test split ─► exact match · edit distance · BLEU
```

## Milestones

- [ ] **1. Data** – samples to image chat messages (`data.py`)
- [ ] **2. Baseline** – transcribe with the base model (`infer.py`)
- [ ] **3. Train** – LoRA fine-tune in Colab (`gpu/finetune_qwen2_vl_latex_unsloth.ipynb`)
- [ ] **4. Metrics** – normalise, exact match, edit distance, BLEU (`metrics.py`)
- [ ] **5. Eval** – score base vs fine-tuned (`eval/run_eval.py`)

## Run it

Train in Colab with `gpu/finetune_qwen2_vl_latex_unsloth.ipynb`, then download the adapter folder.

```bash
pip install -r requirements.txt

PYTHONPATH=src python -m latex_ocr formula.png
PYTHONPATH=src python -m latex_ocr formula.png --adapter outputs/qwen2-vl-latex/adapter
```

## Score it

```bash
PYTHONPATH=src python eval/run_eval.py --limit 100
PYTHONPATH=src python eval/run_eval.py --limit 100 --adapter outputs/qwen2-vl-latex/adapter
pytest -q tests
```

| Part | Weight | Checks |
|---|---|---|
| Exact match | 40% | normalised LaTeX is identical |
| Edit distance | 40% | 1 − normalised edit distance |
| BLEU | 20% | token-level BLEU-4 over LaTeX tokens |

## Leaderboard

| Builder | Model | Score |
|---|---|---|
| | | |

## Stretch goals

- Render predictions with matplotlib's mathtext and compare images instead of strings
- Try the 7B model and compare the gain against the cost
- Handwritten formulas
