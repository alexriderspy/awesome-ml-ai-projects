import json
import re
from dataclasses import dataclass, field
from datetime import date

from .data import DataSource
from .llm import ChatModel
from .metrics import Metrics, comparison_table
from .tools import TOOL_SCHEMAS, Toolbox

NARRATIVE_SECTIONS = ["## Summary", "## Price performance", "## Risk", "## Fundamentals", "## Caveats"]

SYSTEM = """You are a stock research assistant. You describe and compare stocks; you never recommend buying, selling or holding.

Use the tools to gather data for every ticker the user names. A good order: compute_metrics and get_fundamentals for each ticker (you may call several tools at once), then compare with all tickers.

Rules for numbers:
- Never do arithmetic. Do not add, subtract, average, or compute differences or ratios yourself.
- Only quote numbers exactly as the tools returned them, including sign, decimals, $ and % (e.g. "+12.3%", "$415.20", "$3,120.5B", "28.4").
- To say which stock is higher or lower on a metric, use the rankings from the compare tool.

When you have the data, reply with markdown containing exactly these sections, in this order:
## Summary
## Price performance
## Risk
## Fundamentals
## Caveats

Keep it under 450 words. Caveats should mention data limits (one year of history, figures as reported by Yahoo Finance, past performance does not predict future returns).
Do not add a title, comparison table or disclaimer: the program adds those."""

ADVICE_RE = re.compile(
    r"\b(you should (buy|sell|hold|invest)|we recommend|i recommend|strong buy|(is|are) a (buy|sell)\b|"
    r"buy rating|sell rating|price target|good investment|undervalued|overvalued|must[- ]own|outperform rating)",
    re.I,
)
NUM_RE = re.compile(r"[-+−]?\$?\d[\d,]*(?:\.\d+)?%?")

DISCLAIMER = (
    "**Not financial advice.** This report is generated automatically for learning purposes. "
    "It describes past data and is not a recommendation to buy, sell or hold any security. "
    "Data may be delayed or wrong. Do your own research or talk to a licensed adviser."
)


@dataclass
class TraceStep:
    step: int
    tool: str
    arguments: str
    result: str


@dataclass
class RunResult:
    report: str
    narrative: str
    trace: list[TraceStep] = field(default_factory=list)
    metrics: list[Metrics] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    repairs: int = 0
    stopped_reason: str = "done"


def number_key(token: str) -> tuple[str, bool]:
    t = token.replace("−", "-").lstrip("+-").replace("$", "").replace(",", "")
    return t.rstrip("%"), t.endswith("%")


def metric_numbers(text: str) -> list[str]:
    out = []
    for m in NUM_RE.finditer(text):
        tok = m.group(0)
        if "." in tok or "%" in tok or "$" in tok:
            out.append(tok)
    return out


def allowed_numbers(texts: list[str]) -> set[tuple[str, bool]]:
    return {number_key(t) for text in texts for t in metric_numbers(text)}


def check_narrative(narrative: str, allowed: set[tuple[str, bool]]) -> list[str]:
    problems = [f"missing section {s!r}" for s in NARRATIVE_SECTIONS if s not in narrative]
    for m in ADVICE_RE.finditer(narrative):
        problems.append(f"advice-like phrase {m.group(0)!r}; describe, don't recommend")
    bad = sorted({t for t in metric_numbers(narrative) if number_key(t) not in allowed})
    if bad:
        problems.append("these numbers did not come from any tool result (copy tool numbers exactly, no arithmetic): " + ", ".join(bad))
    return problems


def strip_advice(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(s for s in sentences if not ADVICE_RE.search(s))


def assemble_report(tickers: list[str], narrative: str, metrics: list[Metrics]) -> str:
    window = f"{metrics[0].start_date} to {metrics[0].end_date}" if metrics else "n/a"
    names = ", ".join(f"{m.name} ({m.ticker})" for m in metrics) or ", ".join(tickers)
    parts = [
        f"> {DISCLAIMER}",
        f"# Stock comparison: {' vs '.join(t.upper() for t in tickers)}",
        f"_{names}. Daily closes {window}, data from Yahoo Finance via yfinance. Generated {date.today().isoformat()}._",
        narrative.strip(),
        "## Comparison table\n\n_All values computed in code from the raw data._\n\n" + (comparison_table(metrics) if metrics else "n/a"),
        "## Disclaimer\n\n" + DISCLAIMER,
    ]
    return "\n\n".join(parts) + "\n"


def run(tickers: list[str], llm: ChatModel, source: DataSource, request: str = "", max_steps: int = 12,
        max_repairs: int = 2, log=print) -> RunResult:
    tickers = [t.upper().strip() for t in tickers if t.strip()]
    if len(tickers) < 1:
        raise ValueError("Give at least one ticker")
    box = Toolbox(source)
    user = f"Compare these stocks: {', '.join(tickers)}." + (f"\nFocus: {request}" if request else "")
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    res = RunResult(report="", narrative="")
    tool_outputs: list[str] = []

    narrative = ""
    for step in range(1, max_steps + 1):
        reply = llm.chat(messages, tools=TOOL_SCHEMAS)
        res.prompt_tokens += reply.prompt_tokens
        res.completion_tokens += reply.completion_tokens
        messages.append(reply.as_message())
        if not reply.tool_calls:
            narrative = reply.content
            problems = check_narrative(narrative, allowed_numbers(tool_outputs))
            if problems and res.repairs < max_repairs:
                res.repairs += 1
                log(f"[repair {res.repairs}] " + "; ".join(problems))
                messages.append({"role": "user", "content": "Fix these problems and reply with the full corrected markdown:\n- " + "\n- ".join(problems)})
                continue
            break
        for call in reply.tool_calls:
            out = box.call(call.name, call.arguments)
            tool_outputs.append(out)
            res.trace.append(TraceStep(step, call.name, call.arguments, out))
            log(f"[step {step}] {call.name}({call.arguments}) -> {out[:120].replace(chr(10), ' ')}...")
            messages.append({"role": "tool", "tool_call_id": call.id, "content": out})
    else:
        res.stopped_reason = "max_steps"

    if not narrative:
        narrative = "## Summary\nThe agent ran out of steps before writing a summary. See the table below."
    if ADVICE_RE.search(narrative):
        narrative = "\n".join(strip_advice(line) if ADVICE_RE.search(line) else line for line in narrative.splitlines())

    for t in tickers:
        try:
            res.metrics.append(box.metrics(t))
        except Exception as e:
            log(f"[skip] {t}: {e}")
    res.narrative = narrative
    res.report = assemble_report(tickers, narrative, res.metrics)
    return res


def trace_markdown(res: RunResult) -> str:
    lines = ["| Step | Tool | Arguments | Result (start) |", "|---|---|---|---|"]
    for t in res.trace:
        short = t.result[:90].replace("\n", " ").replace("|", "\\|")
        lines.append(f"| {t.step} | `{t.tool}` | `{t.arguments}` | {short}… |")
    return "\n".join(lines)


def trace_json(res: RunResult) -> str:
    return json.dumps([t.__dict__ for t in res.trace], indent=1)
