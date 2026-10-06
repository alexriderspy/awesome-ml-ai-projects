# Dependency Doctor

Checks a `requirements.txt` or `pyproject.toml` for problems: stdlib modules installed from PyPI, backports you no longer need, unpinned and duplicate entries, and yanked releases. Rules find the problems; an LLM only explains them.

Real output for [`demo/requirements.txt`](demo/requirements.txt) with `--python 3.12`:

| Severity | Code | Package | Problem |
|---|---|---|---|
| error | DD008 | `requests` | `requests==2.32.1` was yanked from PyPI |
| error | DD001 | `uuid` | a standard-library module listed as a dependency |
| warning | DD004 | `httpx` | no version constraint |
| warning | DD002 | `mock` | stdlib has had this since Python 3.3 |
| warning | DD006 | `pyyaml` | listed twice |

Full run with LLM explanations: [`demo/run.md`](demo/run.md)

**Level:** Beginner · **Time:** ~2 hours · **Runs on:** laptop; checks need no model, `--explain` uses Ollama or any OpenAI-compatible API

## What you'll learn

- Parsing requirements properly with `packaging` and `tomllib`
- Using the PyPI JSON API with a disk cache
- Splitting work: deterministic checks find, the LLM explains
- Holding an LLM to a contract (same findings, nothing extra) with a retry and a fallback

## How it works

```
manifest ─► parse ─► checks (no LLM): stdlib · backport · py2 compat · unpinned · duplicate · conflict
                                       yanked / missing  ◄── PyPI JSON (cached)
         ─► --explain: LLM rewrites each finding ─► validator ─► retry once, else use the plain text
```

## Milestones

- [ ] **1. Parse** – requirements files and pyproject tables (`manifest.py`)
- [ ] **2. Offline checks** – stdlib, backports, pins, duplicates, conflicts (`checks.py`)
- [ ] **3. PyPI** – yanked and missing releases, cached (`pypi.py`)
- [ ] **4. Explain** – LLM explanations checked against the findings (`explain.py`)
- [ ] **5. Eval** – score 90+ (`eval/run_eval.py`)

## Run it

```bash
pip install -r requirements.txt

PYTHONPATH=src python -m dep_doctor demo/requirements.txt --python 3.12
PYTHONPATH=src python -m dep_doctor demo/requirements.txt --python 3.12 --explain
```

Exits with code 1 on any error-level finding, so it can gate CI.

## Score it

```bash
PYTHONPATH=src python eval/run_eval.py            # checks + explanations
PYTHONPATH=src python eval/run_eval.py --no-llm   # checks only
pytest -q
```

8 original manifests with hand-written expected findings. PyPI answers are cached so the eval runs offline.

| Part | Weight | Checks |
|---|---|---|
| Findings | 80% | F1 of (code, package) pairs |
| Explanations | 20% | the LLM covers exactly the findings |

## Leaderboard

| Builder | Model | Score |
|---|---|---|
| reference | deepseek-flash | 100.0 |

## Stretch goals

- Read `uv.lock` / `poetry.lock` and check resolved versions
- Flag known vulnerabilities with the OSV API
- `--fix`: write a cleaned manifest
