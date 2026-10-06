# Coding Agent that Fixes Failing Tests

A small agent that reads a repo with failing tests, edits the code and runs pytest until everything passes. It is not allowed to touch the tests.

From a real run ([full transcript](demo/run.md)):

```
$ PYTHONPATH=src python -m mini_coder parcel-weights
[step 1] list_files({})
[step 2] read_file(tests/test_parcels.py), read_file(parcels/shipping.py), ...
[step 3] write_file(parcels/units.py), write_file(parcels/shipping.py)
[step 4] run_tests({})  -> ALL TESTS PASSED
tests pass: True  tests untouched: True  SOLVED: True
```

**Level:** Intermediate · **Time:** ~4 hours · **Runs on:** laptop (Ollama) or any OpenAI-compatible API with tool calling

## What you'll learn

- An agent loop on plain tool calling, no framework
- Tools that can only touch a temporary copy of the repo
- Catching the two classic cheats: editing tests and escaping the folder
- Building a small benchmark where every task is checked to be broken and fixable

## How it works

```
tasks/<name>/ ─► copy to a temp sandbox ◄── list_files · read_file · write_file · run_tests
issue text ─► LLM ─► agent loop (step cap, trace, tokens)
judge: every test file unchanged (sha256) AND a fresh pytest run passes
```

This guards against an over-eager model, not malicious code. Use a container for untrusted code.

## Milestones

- [ ] **1. Tasks** – 15 original bugs, each a tiny package with failing tests (`tasks/`)
- [ ] **2. Sandbox** – temp copy, path checks, test-file hashing (`sandbox.py`)
- [ ] **3. Tools** – the four tools with JSON schemas (`tools.py`)
- [ ] **4. Agent loop** – step cap, trace, token count (`agent.py`)
- [ ] **5. Eval** – solve all 15 tasks (`eval/run_eval.py`)

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env && export $(xargs < .env)

PYTHONPATH=src python -m mini_coder pagination
PYTHONPATH=src python -m mini_coder path/to/repo --issue "dates are off by one"
```

The 15 tasks cover off-by-one errors, mutable defaults, float rounding, regex bugs, recursion base cases and a two-file bug. See `tasks/`.

## Score it

```bash
PYTHONPATH=src python eval/run_eval.py
pytest -q
```

Score = share of tasks solved (tests pass and test files unchanged). Average steps and tokens are reported too. Results: [`demo/results.md`](demo/results.md).

## Leaderboard

| Builder | Model | Score |
|---|---|---|
| reference | deepseek-flash | 100.0 |

## Stretch goals

- Harder tasks: bugs spread over several files, misleading issue text
- A `search` tool and an `edit_file` tool that patches a snippet
- Run tests in a Docker container with no network
