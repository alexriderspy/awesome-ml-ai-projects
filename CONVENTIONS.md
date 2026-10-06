# Project conventions

Every project in this repo follows the same shape so people can move between them easily.
The reference implementation is [`projects/llm-apps/youtube-summarizer`](projects/llm-apps/youtube-summarizer). Copy its structure.

## Folder layout

```
projects/<category>/<slug>/
  README.md            # see "README" below
  requirements.txt     # pinned loosely (>=)
  .env.example         # LLM_BASE_URL / LLM_API_KEY / LLM_MODEL, plus any project-specific keys
  src/<package>/       # the reference implementation, importable with PYTHONPATH=src
    llm.py             # OpenAI-compatible chat wrapper (copy from the summarizer, extend if needed)
    __main__.py        # CLI entry point: python -m <package> ...
  app.py               # Streamlit UI, when a UI makes sense
  .streamlit/config.toml  # monochrome theme (copy from the summarizer)
  eval/
    practice/          # small, ORIGINAL practice set (never copyrighted text or scraped data)
    run_eval.py        # prints per-case scores and "OVERALL <n>/100"
  tests/               # pytest, fully offline: no network, no API keys, no GPU (use fakes)
  demo/                # real outputs from a real run (see "Demo")
```

## Models

- Every LLM call goes through `llm.py`, an OpenAI-compatible client configured by `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`.
- Default to local Ollama (`http://localhost:11434/v1`, `llama3.2`) so nobody needs a credit card.
- Embeddings: prefer a local model (`sentence-transformers/all-MiniLM-L6-v2`) or a pure-Python fallback (TF-IDF / BM25) so tests stay offline.
- Classic ML projects use scikit-learn / PyTorch and need no LLM.

## README

Sections, in this order:

1. Title and a one-sentence pitch
2. Demo image or demo output (from `demo/`)
3. `**Level:** · **Time:** · **Runs on:**` line
4. `Video:` link, only for projects that have a video
5. What you'll learn (4 short bullets)
6. How it works (a small ASCII diagram)
7. Milestones (4–6 checkboxes, each naming the file it lives in)
8. Run it (copy-pasteable commands)
9. Score it (what the eval measures and the weights, in a table)
10. Leaderboard (table with the reference row)
11. Stretch goals (3 bullets)

Plain, direct English. No hype words, no emoji, no long caveat paragraphs. Keep it under ~100 lines.

## Eval

- Deterministic where possible (exact match, F1, NDCG, timestamp/citation validity, schema validation, test pass rate).
- LLM-as-judge only when nothing deterministic works, and say so in the README.
- Output: per-case lines plus a final `OVERALL <n>/100` line.

## Demo

- Run the project for real (the maintainers use `deepseek-flash` through `https://api.deepseek.com`) and commit the outputs under `demo/`.
- Streamlit apps: capture a screenshot with `tools/screenshot_streamlit.py`.
- CLI tools: save the command and its real output as markdown.
- Never fake a demo. If something can't run here (for example GPU training), run the smallest honest version (a tiny model for a few CPU steps) and say so plainly in the README.

## Data and licences

- Practice sets are written for this repo, or come from datasets with a permissive licence (cite it in the README).
- Don't commit large data; download it in code.
- Never commit API keys or `.env` files.
