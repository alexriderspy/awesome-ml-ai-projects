import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .agent import AgentResult, run_agent
from .llm import ChatModel
from .sandbox import Sandbox, run_pytest

TASKS_DIR = Path(__file__).resolve().parents[2] / "tasks"


@dataclass
class Task:
    name: str
    path: Path
    issue: str


def load_task(path: str | Path, issue: str | None = None) -> Task:
    path = Path(path).resolve()
    meta = path / "task.json"
    if issue is None:
        issue = json.loads(meta.read_text())["issue"] if meta.exists() else "Some tests fail."
    return Task(path.name, path, issue)


def load_tasks(root: Path = TASKS_DIR) -> list[Task]:
    return [load_task(p) for p in sorted(root.iterdir()) if (p / "task.json").exists()]


def judge(sb: Sandbox, test_timeout: int = 30) -> dict:
    tampered = sb.tampered()
    passed, output = run_pytest(sb.root, timeout=test_timeout)
    return {"solved": passed and not tampered, "tests_pass": passed, "tampered": tampered, "output": output}


def solve(task: Task, llm: ChatModel, max_steps: int = 20, keep: bool = False,
          on_event: Callable[[dict], None] | None = None) -> tuple[AgentResult, dict]:
    with Sandbox(task.path, keep=keep) as sb:
        result = run_agent(llm, sb, task.issue, max_steps=max_steps, on_event=on_event)
        verdict = judge(sb)
        verdict["sandbox"] = str(sb.root) if keep else None
    return result, verdict
