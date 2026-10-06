import argparse
import json
from pathlib import Path

from .llm import OpenAICompatible
from .tasks import TASKS_DIR, load_task, solve


def show(event: dict) -> None:
    if event["type"] == "thought":
        print(f"\n[step {event['step']}] model: {event['text'].strip()}")
        return
    args = dict(event["args"])
    if "content" in args:
        args["content"] = f"<{len(args['content'])} chars>"
    print(f"\n[step {event['step']}] {event['tool']}({json.dumps(args)})")
    if event["tool"] == "write_file" and "content" in event["args"]:
        print("```python\n" + event["args"]["content"].rstrip() + "\n```")
    out = event["full_result"]
    lines = out.splitlines()
    if len(lines) > 25:
        out = "\n".join(lines[:12] + ["..."] + lines[-10:])
    print("  -> " + out.replace("\n", "\n     "))


def main() -> None:
    ap = argparse.ArgumentParser(description="Fix failing tests with an LLM agent")
    ap.add_argument("target", help="task name under tasks/ or a path to a repo folder")
    ap.add_argument("--issue", help="issue text (defaults to the task's task.json)")
    ap.add_argument("--max-steps", type=int, default=20)
    ap.add_argument("--keep", action="store_true", help="keep the sandbox folder to inspect it")
    ap.add_argument("--trace", help="write the tool-call trace as JSON here")
    args = ap.parse_args()

    path = TASKS_DIR / args.target if (TASKS_DIR / args.target).is_dir() else Path(args.target)
    task = load_task(path, args.issue)
    print(f"task: {task.name}\nissue: {task.issue}")

    result, verdict = solve(task, OpenAICompatible(), max_steps=args.max_steps, keep=args.keep, on_event=show)

    print(f"\nstopped: {result.stopped} after {result.steps} steps, {result.tokens} tokens "
          f"({result.prompt_tokens} prompt + {result.completion_tokens} completion)")
    print(f"tests pass: {verdict['tests_pass']}  tests untouched: {not verdict['tampered']}  "
          f"SOLVED: {verdict['solved']}")
    if verdict["sandbox"]:
        print(f"sandbox kept at {verdict['sandbox']}")
    if args.trace:
        Path(args.trace).write_text(json.dumps(result.trace, indent=2))


if __name__ == "__main__":
    main()
