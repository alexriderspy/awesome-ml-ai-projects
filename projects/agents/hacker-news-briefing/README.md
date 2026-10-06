# Hacker News Briefing

Ranks the Hacker News front page against your interests and writes a short daily brief, with a "why it matters to you" line per story.

Real output from 2026-10-06 ([full brief](demo/brief-2026-10-06.md), [run log](demo/run.md)):

```markdown
## 3. [Texas city demands $2M for public records on Flock usage](https://arstechnica.com/...)

`arstechnica.com` · 194 points · 29 comments · matched: privacy and surveillance

A Texas city is charging about $2M to fulfil a public records request about its Flock cameras.

**Why it matters to you:** You care about privacy and surveillance, so watch how agencies price these requests.
```

**Level:** Intermediate · **Time:** ~3 hours · **Runs on:** laptop (Ollama) or any OpenAI-compatible API

## What you'll learn

- Reading the official HN API with timeouts and parallel fetches
- Ranking with BM25 against a YAML interest profile
- Adding an LLM rerank and measuring whether it helps (NDCG)
- Running a script on a schedule

## How it works

```
topstories.json ─► 60 items in parallel ─► BM25 vs your profile (+ popularity, - dislikes)
   ─► optional LLM rerank of the top 15 ─► fetch comments + page text for the top K
   ─► LLM: summary + "why it matters" per story ─► briefs/YYYY-MM-DD.md (Slack optional)
```

## Milestones

- [ ] **1. Fetch** – top stories in parallel, skip jobs and dead posts (`hn.py`)
- [ ] **2. Profile** – interests, weights and dislikes from YAML (`profile.py`)
- [ ] **3. Rank** – BM25, popularity prior, optional LLM rerank (`rank.py`)
- [ ] **4. Summarize** – 1-3 sentences and a "why" line per story (`summarize.py`)
- [ ] **5. Deliver** – markdown brief, Slack behind a flag (`brief.py`, `slack.py`)
- [ ] **6. Eval** – NDCG@5 above 0.95 (`eval/run_eval.py`)

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env && export $(xargs < .env)

PYTHONPATH=src python -m hn_brief --profile profiles/example.yaml
PYTHONPATH=src python -m hn_brief --profile profiles/example.yaml --rerank --comments --pages
```

Edit `profiles/example.yaml` first. To run it daily, add a cron entry:

```cron
30 7 * * * cd /path/to/hacker-news-briefing && PYTHONPATH=src python -m hn_brief --profile profiles/example.yaml
```

## Score it

```bash
PYTHONPATH=src python eval/run_eval.py            # with LLM
PYTHONPATH=src python eval/run_eval.py --no-llm   # BM25 only
pytest -q tests
```

4 original interest profiles × 2 story sets (30 real stories saved on 2026-10-06, 20 made-up ones), hand-labelled.

| Part | Weight | Checks |
|---|---|---|
| Ranking | 50% | NDCG@5 against the labels |
| Format | 30% | summary 1-3 sentences, "why" line one sentence |
| Key terms | 20% | summary mentions the story's key terms |

## Leaderboard

| Builder | Model | Score |
|---|---|---|
| reference | deepseek-flash | 98.3 |
| reference | BM25 only | 97.4 |

## Stretch goals

- Learn from what you click and adjust the weights
- Swap BM25 for local embeddings and compare NDCG
- Skip stories already sent in earlier briefs
