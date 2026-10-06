import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from mini_coder.agent import run_agent
from mini_coder.sandbox import Sandbox, is_protected, run_pytest
from mini_coder.tasks import TASKS_DIR, judge, load_task, load_tasks, solve
from mini_coder.tools import Toolbox
from run_eval import overall, SOLUTIONS

TASKS = load_tasks()
FIXED_PAGER = (SOLUTIONS / "pagination/pager/pages.py").read_text()


class FakeLLM:

    def __init__(self, turns):
        self.turns = list(turns)
        self.seen = []

    def chat(self, messages, tools=None):
        self.seen.append(list(messages))
        turn = self.turns.pop(0)
        if isinstance(turn, str):
            return {"content": turn, "tool_calls": [], "usage": {"prompt_tokens": 100, "completion_tokens": 10},
                    "message": {"role": "assistant", "content": turn}}
        calls = [{"id": f"c{i}", "name": n, "arguments": a} for i, (n, a) in enumerate(turn)]
        return {"content": "", "tool_calls": calls, "usage": {"prompt_tokens": 100, "completion_tokens": 10},
                "message": {"role": "assistant", "content": ""}}


def test_task_set_shape():
    assert len(TASKS) >= 15
    for t in TASKS:
        assert t.issue.strip()
        assert any(is_protected(p.relative_to(t.path)) for p in t.path.rglob("test_*.py"))
        assert (SOLUTIONS / t.name).is_dir(), f"no reference solution for {t.name}"


def apply_solution(name: str, dest: Path) -> None:
    for f in (SOLUTIONS / name).rglob("*"):
        if f.is_file():
            target = dest / f.relative_to(SOLUTIONS / name)
            assert target.exists(), f"solution adds a new file {target}"
            shutil.copy(f, target)


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.name)
def test_task_fails_as_shipped_and_passes_with_reference(task):
    with Sandbox(task.path) as sb:
        passed, out = run_pytest(sb.root)
        assert not passed, f"{task.name} should fail as shipped:\n{out}"
        apply_solution(task.name, sb.root)
        verdict = judge(sb)
        assert verdict["solved"], f"{task.name} reference fix does not pass:\n{verdict['output']}"


def test_solutions_only_touch_source_files():
    for task_dir in SOLUTIONS.iterdir():
        for f in task_dir.rglob("*.py"):
            assert not is_protected(f.relative_to(task_dir)), f


def test_fake_llm_fixes_pagination():
    task = load_task(TASKS_DIR / "pagination")
    llm = FakeLLM([
        [("list_files", {})],
        [("read_file", {"path": "tests/test_pages.py"}), ("read_file", {"path": "pager/pages.py"})],
        [("run_tests", {})],
        [("write_file", {"path": "pager/pages.py", "content": FIXED_PAGER})],
        [("run_tests", {})],
        "Fixed the 1-based page offset and rounded page_count up.",
    ])
    result, verdict = solve(task, llm)
    assert verdict == {**verdict, "solved": True, "tests_pass": True, "tampered": []}
    assert result.stopped == "done" and result.steps == 6
    assert result.tokens == 6 * 110
    assert [t["tool"] for t in result.trace] == ["list_files", "read_file", "read_file", "run_tests",
                                                  "write_file", "run_tests"]
    assert "FAILED" in result.trace[3]["result"] and "PASSED" in result.trace[5]["result"]
    assert "number * size" in (TASKS_DIR / "pagination/pager/pages.py").read_text()
    last = llm.seen[-1][-1]
    assert last["role"] == "tool" and last["tool_call_id"] == "c0"


def test_step_cap():
    task = load_task(TASKS_DIR / "pagination")
    llm = FakeLLM([[("list_files", {})]] * 5)
    result, verdict = solve(task, llm, max_steps=3)
    assert result.stopped == "step_cap" and result.steps == 3
    assert not verdict["solved"]


def test_token_estimate_when_no_usage():
    class NoUsage(FakeLLM):
        def chat(self, messages, tools=None):
            r = super().chat(messages, tools)
            r["usage"] = {}
            return r

    with Sandbox(TASKS_DIR / "pagination") as sb:
        res = run_agent(NoUsage(["done"]), sb, "issue")
    assert res.tokens > 0


def test_write_file_refuses_tests_and_test_config():
    with Sandbox(TASKS_DIR / "pagination") as sb:
        tb = Toolbox(sb)
        for path in ["tests/test_pages.py", "tests/new_helper.py", "conftest.py", "pager/conftest.py",
                     "pytest.ini", "pyproject.toml", "pytest.py", "sitecustomize.py", "test_extra.py"]:
            assert tb.call("write_file", {"path": path, "content": "x"}).startswith("REFUSED"), path
        assert sb.tampered() == []
        assert tb.call("write_file", {"path": "pager/helpers.py", "content": "X = 1\n"}).startswith("wrote")


def test_tamper_detected_after_run():
    task = load_task(TASKS_DIR / "pagination")
    cheat = FIXED_PAGER.replace("def page_count", "def _unused") + (
        "\nimport pathlib\n"
        "_t = pathlib.Path(__file__).parents[1] / 'tests' / 'test_pages.py'\n"
        "_t.write_text('def test_ok():\\n    assert True\\n')\n"
        "def page_count(items, size):\n    return 0\n"
    )
    llm = FakeLLM([[("write_file", {"path": "pager/pages.py", "content": cheat})], [("run_tests", {})], "done"])
    result, verdict = solve(task, llm)
    assert verdict["tests_pass"] is True
    assert verdict["tampered"] == ["tests/test_pages.py"]
    assert verdict["solved"] is False


def test_tamper_detects_added_and_deleted_files():
    with Sandbox(TASKS_DIR / "slugify") as sb:
        (sb.root / "conftest.py").write_text("collect_ignore = ['tests']\n")
        (sb.root / "tests/test_slug.py").unlink()
        assert sb.tampered() == ["conftest.py", "tests/test_slug.py"]


@pytest.mark.parametrize("path", ["../escape.py", "pager/../../x.py", "/etc/passwd", "~/x", "",
                                  "../../../../../../tmp/x"])
def test_path_traversal_refused(path):
    with Sandbox(TASKS_DIR / "pagination") as sb:
        tb = Toolbox(sb)
        assert tb.call("read_file", {"path": path}).startswith("REFUSED")
        assert tb.call("write_file", {"path": path, "content": "x"}).startswith("REFUSED")


def test_symlink_escape_refused(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("nope")
    with Sandbox(TASKS_DIR / "pagination") as sb:
        (sb.root / "link").symlink_to(tmp_path)
        assert Toolbox(sb).call("read_file", {"path": "link/secret.txt"}).startswith("REFUSED")


def test_sandbox_is_a_copy_and_is_cleaned_up():
    with Sandbox(TASKS_DIR / "pagination") as sb:
        root = sb.root
        assert not (root / "task.json").exists()
        Toolbox(sb).call("write_file", {"path": "pager/pages.py", "content": "BROKEN"})
    assert not root.exists()
    assert "def get_page" in (TASKS_DIR / "pagination/pager/pages.py").read_text()


def test_run_tests_timeout(tmp_path):
    (tmp_path / "test_slow.py").write_text("def test_spin():\n    while True:\n        pass\n")
    passed, out = run_pytest(tmp_path, timeout=2)
    assert not passed and "TIMEOUT" in out


def test_unknown_tool_and_missing_file():
    with Sandbox(TASKS_DIR / "pagination") as sb:
        tb = Toolbox(sb)
        assert tb.call("rm_rf", {}).startswith("ERROR")
        assert tb.call("read_file", {"path": "nope.py"}).startswith("ERROR")


def test_overall_is_solve_rate():
    rows = [{"solved": True}, {"solved": False}, {"solved": True}, {"solved": True}]
    assert overall(rows) == 75.0
