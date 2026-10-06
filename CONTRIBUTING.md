# Contributing

## Post your score

Every project has a practice eval and a leaderboard in its README.

1. Build the project (or improve the reference) in your fork.
2. Run its eval: `PYTHONPATH=src python eval/run_eval.py`
3. Open a pull request that adds one row to that project's leaderboard: your GitHub handle, the model you used, your score, and a link to your code.

Scores on the practice set are self-reported. Don't tune your prompts on the practice cases themselves; that only fools you.

## Add a project

Follow [CONVENTIONS.md](CONVENTIONS.md). A new project needs a working implementation, an original practice set, an eval that prints `OVERALL <n>/100`, offline tests, and a real demo.

## Fix something

Bug reports and fixes are welcome. Keep pull requests to one project at a time.
