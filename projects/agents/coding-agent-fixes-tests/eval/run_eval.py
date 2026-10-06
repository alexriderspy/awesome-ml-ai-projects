import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mini_coder.tasks import load_tasks, solve

SOLUTIONS = Path(__file__).parent / "solutions"


def overall(rows: list[dict]) -> float:
    return round(100 * sum(r["solved"] for r in rows) / len(rows), 1) if rows else 0.0


def run_one(task, llm, max_steps: int) -> dict:
    t0 = time.time()
    try:
        result, verdict = solve(task, llm, max_steps=max_steps)
    except Exception as e:
        return {"task": task.name, "solved": False, "tests_pass": False, "tampered": [], "steps": 0,
                "tokens": 0, "stopped": f"error: {type(e).__name__}: {e}"[:200], "seconds": 0, "trace": []}
    return {"task": task.name, "solved": verdict["solved"], "tests_pass": verdict["tests_pass"],
            "tampered": verdict["tampered"], "steps": result.steps, "tokens": result.tokens,
            "stopped": result.stopped, "seconds": round(time.time() - t0, 1), "trace": result.trace}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", nargs="*", help="only these task names")
    ap.add_argument("--max-steps", type=int, default=20)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--results-md", help="also write a markdown results table here")
    ap.add_argument("--traces", help="write every tool-call trace as JSON here")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    from mini_coder.llm import OpenAICompatible

    llm = OpenAICompatible()
    tasks = [t for t in load_tasks() if not args.tasks or t.name in args.tasks]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(lambda t: run_one(t, llm, args.max_steps), tasks))

    score = overall(rows)
    avg_steps = round(sum(r["steps"] for r in rows) / len(rows), 1)
    avg_tokens = round(sum(r["tokens"] for r in rows) / len(rows))
    if args.json:
        print(json.dumps({"overall": score, "avg_steps": avg_steps, "avg_tokens": avg_tokens,
                          "cases": [{k: v for k, v in r.items() if k != "trace"} for r in rows]}, indent=2))
    else:
        for r in rows:
            flag = "SOLVED" if r["solved"] else "failed"
            extra = f"  tampered={','.join(r['tampered'])}" if r["tampered"] else ""
            print(f"{r['task']:20s} {flag:6s}  tests_pass={str(r['tests_pass']):5s}  steps={r['steps']:2d}  "
                  f"tokens={r['tokens']:6d}  stopped={r['stopped']}{extra}")
        print(f"\nsolved {sum(r['solved'] for r in rows)}/{len(rows)}  avg steps {avg_steps}  avg tokens {avg_tokens}")
        print(f"\nOVERALL {score}/100")

    if args.results_md:
        lines = ["| task | solved | steps | tokens |", "|---|---|---|---|"]
        lines += [f"| {r['task']} | {'yes' if r['solved'] else 'no'} | {r['steps']} | {r['tokens']} |" for r in rows]
        lines += [f"| **average** | **{sum(r['solved'] for r in rows)}/{len(rows)}** | **{avg_steps}** | "
                  f"**{avg_tokens}** |", "", f"OVERALL {score}/100 (solve rate)"]
        Path(args.results_md).write_text("\n".join(lines) + "\n")
    if args.traces:
        Path(args.traces).write_text(json.dumps({r["task"]: r["trace"] for r in rows}, indent=2))


if __name__ == "__main__":
    main()
