import json

from .checks import Finding
from .llm import ChatModel, parse_json

SYSTEM = """You explain dependency problems to a developer in plain words.
You get a JSON list of findings from a linter. For EACH finding, write one or two
short sentences saying why it matters and what to do.
Reply with a JSON array only, one object per finding, in the same order:
[{"code": "...", "package": "...", "explanation": "..."}]
Use exactly the code and package values you were given. Do not add findings,
do not merge findings, do not mention packages that are not in the list."""


def _check(items, findings: list[Finding]) -> list[str]:
    if not isinstance(items, list):
        return ["reply is not a JSON array"]
    want = [(f.code, f.package) for f in findings]
    got = [(str(i.get("code")), str(i.get("package"))) for i in items if isinstance(i, dict)]
    problems = [f"extra item {g}" for g in got if g not in want]
    problems += [f"missing item {w}" for w in want if w not in got]
    if len(got) != len(set(got)):
        problems.append("duplicate items")
    return problems


def explain(findings: list[Finding], llm: ChatModel, retries: int = 1) -> tuple[list[dict], list[str]]:
    log: list[str] = []
    if not findings:
        return [], log
    payload = json.dumps([{"code": f.code, "package": f.package, "message": f.message, "fix": f.fix} for f in findings], indent=1)
    user = payload
    items = None
    for attempt in range(retries + 1):
        reply = llm.complete(SYSTEM, user)
        try:
            items = parse_json(reply)
        except ValueError:
            items = None
        problems = _check(items, findings) if items is not None else ["reply had no JSON"]
        log.append(f"attempt {attempt + 1}: " + ("ok" if not problems else "; ".join(problems)))
        if not problems:
            break
        user = payload + "\n\nYour previous reply was rejected: " + "; ".join(problems) + ". Try again."

    by_key = {}
    for i in items or []:
        if isinstance(i, dict) and (i.get("code"), i.get("package")) not in by_key:
            by_key[(i.get("code"), i.get("package"))] = str(i.get("explanation", "")).strip()
    out = []
    for f in findings:
        text = by_key.get((f.code, f.package)) or f"{f.message} {f.fix}"
        out.append({"code": f.code, "package": f.package, "explanation": text})
    return out, log


def render_markdown(path: str, py: str, findings: list[Finding], explained: list[dict] | None = None) -> str:
    lines = [f"# Dependency check: `{path}`", "", f"Target Python: {py} · {len(findings)} finding(s)", ""]
    if not findings:
        return "\n".join(lines + ["No problems found."])
    expl = {(e["code"], e["package"]): e["explanation"] for e in explained or []}
    lines += ["| Severity | Code | Package | Line | Problem |", "|---|---|---|---|---|"]
    for f in findings:
        lines.append(f"| {f.severity} | {f.code} | `{f.package}` | {f.line or '-'} | {f.message.replace('|', '/')} |")
    lines += ["", "## What to do", ""]
    for f in findings:
        lines.append(f"- **{f.package}** ({f.code}): {expl.get((f.code, f.package)) or f.fix}")
    return "\n".join(lines)
