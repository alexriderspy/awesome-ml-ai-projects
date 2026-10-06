import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tool_calling.agent import AgentResult, TraceEntry, format_entry, run_agent
from tool_calling.notes import NotesStore
from tool_calling.toolbox import default_tools
from tool_calling.weather import WeatherError

PRACTICE = Path(__file__).parent / "practice"
NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def load_tasks() -> list[dict]:
    return json.loads((PRACTICE / "tasks.json").read_text())


def stub_weather(city: str) -> dict:
    data = json.loads((PRACTICE / "weather_stub.json").read_text())
    key = city.split(",")[0].strip().lower()
    if key not in data:
        raise WeatherError(f"no place called {city!r} found")
    return data[key]


def numbers_in(text: str) -> list[float]:
    text = re.sub(r"(?<=\d),(?=\d{3})", "", text)
    return [float(n) for n in NUM_RE.findall(text)]


def answer_score(answer: str, spec: dict, notes: NotesStore | None = None) -> float:
    parts = []
    found = numbers_in(answer)
    for value, tol in spec.get("numbers", []):
        parts.append(1.0 if any(abs(f - value) <= tol for f in found) else 0.0)
    low = answer.lower()
    for group in spec.get("contains", []):
        parts.append(1.0 if any(p.lower() in low for p in group) else 0.0)
    if "notes_contain" in spec:
        hit = notes is not None and any(spec["notes_contain"].lower() in n["text"].lower() for n in notes.all())
        parts.append(1.0 if hit else 0.0)
    return sum(parts) / len(parts) if parts else 0.0


def tool_score(trace: list[TraceEntry], task: dict) -> float:
    expected = set(task["tools"])
    alts = task.get("alt_tools", {})
    called = set()
    for e in trace:
        sub = next((exp for exp, options in alts.items() if e.tool in options), None)
        called.add(sub or e.tool)
    if not expected and not called:
        return 1.0
    score = len(expected & called) / len(expected | called)
    if task.get("parallel"):
        per_step: dict[int, int] = {}
        for e in trace:
            if e.tool == task["parallel"]:
                per_step[e.step] = per_step.get(e.step, 0) + 1
        if max(per_step.values(), default=0) < 2:
            score *= 0.5
    return score


def score(result: AgentResult, task: dict, notes: NotesStore | None = None) -> dict:
    a = answer_score(result.answer, task["answer"], notes)
    t = tool_score(result.trace, task)
    return {"answer": a, "tools": t, "score": round(100 * (0.7 * a + 0.3 * t), 1),
            "called": [e.tool for e in result.trace], "steps": result.steps}


def run_task(task: dict, llm, workdir: Path) -> tuple[AgentResult, dict]:
    notes_path = workdir / f"{task['id']}-notes.json"
    shutil.copy(PRACTICE / "notes_seed.json", notes_path)
    tools = default_tools(notes_path, weather_fetch=stub_weather)
    result = run_agent(task["question"], llm, tools)
    return result, score(result, task, NotesStore(notes_path))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    from tool_calling.llm import OpenAICompatible

    llm = OpenAICompatible()
    results = {}
    with tempfile.TemporaryDirectory() as tmp:
        for task in load_tasks():
            res, results[task["id"]] = run_task(task, llm, Path(tmp))
            if args.verbose and not args.json:
                print(f"--- {task['id']}: {task['question']}")
                for e in res.trace:
                    print("  " + format_entry(e, 120))
                print("  answer: " + res.answer.replace("\n", " ")[:300])

    overall = round(sum(r["score"] for r in results.values()) / len(results), 1)
    if args.json:
        print(json.dumps({"overall": overall, "cases": results}, indent=2))
        return
    for cid, r in results.items():
        print(f"{cid:22s} score={r['score']:5.1f}  answer={r['answer']:.2f}  tools={r['tools']:.2f}  "
              f"steps={r['steps']}  called={','.join(r['called']) or '-'}")
    print(f"\nOVERALL {overall}/100")


if __name__ == "__main__":
    main()
