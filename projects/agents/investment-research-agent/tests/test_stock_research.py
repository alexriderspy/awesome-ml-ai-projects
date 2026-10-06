import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from run_eval import score
from stock_research.agent import (DISCLAIMER, check_narrative, allowed_numbers, metric_numbers,
                                  number_key, run)
from stock_research.data import FixtureSource, PriceBar
from stock_research.llm import Reply, ToolCall
from stock_research.metrics import (annualized_volatility, compute_metrics, max_drawdown,
                                    metrics_for, period_return)
from stock_research.tools import Toolbox

FIX = FixtureSource(ROOT / "eval" / "fixtures")


def test_period_return():
    closes = [100.0] * 30 + [110.0]
    assert period_return(closes, None) == pytest.approx(0.10)
    assert period_return(closes, 21) == pytest.approx(0.10)
    assert period_return([100.0, 110.0], 21) is None


def test_max_drawdown():
    assert max_drawdown([100, 120, 90, 130, 117]) == pytest.approx(90 / 120 - 1)
    assert max_drawdown([1, 2, 3]) == 0.0


def test_volatility_zero_for_constant_growth_and_positive_otherwise():
    assert annualized_volatility([100 * 1.01 ** i for i in range(50)]) == pytest.approx(0.0, abs=1e-12)
    assert annualized_volatility([100, 102, 99, 104, 101]) > 0


def test_formatting_rules():
    bars = [PriceBar(f"2025-01-{i + 1:02d}", 100.0 + i) for i in range(25)]
    m = compute_metrics("abc", bars, {"marketCap": 1_234_567_890_123, "trailingPE": 21.456,
                                       "profitMargins": 0.2534, "dividendYield": 2.45, "revenueGrowth": -0.031})
    f = m.formatted
    assert m.ticker == "ABC"
    assert f["last_close"] == "$124.00"
    assert f["return_1y"] == "+24.0%"
    assert f["market_cap"] == "$1,234.6B"
    assert f["trailing_pe"] == "21.5"
    assert f["profit_margin"] == "25.3%"
    assert f["dividend_yield"] == "2.5%"
    assert f["revenue_growth"] == "-3.1%"
    assert f["forward_pe"] == "n/a"


def test_fixtures_load():
    m = metrics_for("KO", FIX)
    assert m.name.startswith("Coca-Cola")
    assert m.formatted["last_close"].startswith("$")


def test_toolbox_errors_go_back_as_text():
    box = Toolbox(FIX)
    assert box.call("nope", "{}").startswith("ERROR: unknown tool")
    assert box.call("compute_metrics", "{not json").startswith("ERROR: bad arguments")
    assert box.call("compute_metrics", '{"symbol": "KO"}').startswith("ERROR: wrong arguments")
    assert "No fixture" in box.call("compute_metrics", '{"ticker": "ZZZZ"}')


def test_compare_has_table_and_rankings():
    out = json.loads(Toolbox(FIX).call("compare", '{"tickers": ["KO", "PEP"]}'))
    assert out["table"].startswith("| Metric | KO | PEP |")
    assert any(r.startswith("1Y return: highest") for r in out["rankings"])


def test_number_extraction_and_keys():
    text = "In 2025 KO returned +34.4% and closed at $86.51; market cap $372.2B; P/E 26.0; 1M window."
    assert metric_numbers(text) == ["+34.4%", "$86.51", "$372.2", "26.0"]
    assert number_key("-34.4%") == number_key("34.4%") == ("34.4", True)
    assert number_key("$3,899.7") == ("3899.7", False)


def test_check_narrative_flags_problems():
    allowed = allowed_numbers(['{"1Y return": "+34.4%"}'])
    good = "\n".join(["## Summary", "KO rose +34.4%.", "## Price performance", "## Risk", "## Fundamentals", "## Caveats"])
    assert check_narrative(good, allowed) == []
    bad = "## Summary\nKO rose 35%. You should buy KO."
    problems = " ".join(check_narrative(bad, allowed))
    assert "missing section" in problems and "advice-like" in problems and "35%" in problems


class FakeLLM:

    def __init__(self, narrative_numbers: dict):
        self.turn = 0
        self.seen: list[list[dict]] = []
        self.n = narrative_numbers

    def chat(self, messages, tools=None):
        self.seen.append(list(messages))
        self.turn += 1
        if self.turn == 1:
            return Reply("", [ToolCall("c1", "compute_metrics", '{"ticker": "KO"}'),
                              ToolCall("c2", "compute_metrics", '{"ticker": "PEP"}'),
                              ToolCall("c3", "compare", '{"tickers": ["KO", "PEP"]}')], 100, 20)
        body = "\n".join(["## Summary", "KO returned {ko} and PEP returned {pep}.", "## Price performance", "x",
                          "## Risk", "x", "## Fundamentals", "x", "## Caveats", "Past performance does not predict future returns."])
        if self.turn == 2:
            return Reply(body.format(ko="+99.9%", pep=self.n["PEP"]), [], 200, 50)
        return Reply(body.format(ko=self.n["KO"], pep=self.n["PEP"]), [], 300, 50)


def test_agent_runs_tools_repairs_and_wraps_report():
    n = {t: metrics_for(t, FIX).formatted["return_1y"] for t in ["KO", "PEP"]}
    llm = FakeLLM(n)
    res = run(["ko", "pep"], llm, FIX, log=lambda s: None)
    assert [t.tool for t in res.trace] == ["compute_metrics", "compute_metrics", "compare"]
    tool_msgs = [m for m in llm.seen[1] if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tool_msgs] == ["c1", "c2", "c3"]
    assert res.repairs == 1 and "+99.9%" in llm.seen[2][-1]["content"]
    assert "+99.9%" not in res.report
    assert res.report.startswith("> " + DISCLAIMER)
    assert res.report.rstrip().endswith(DISCLAIMER)
    assert "| Metric | KO | PEP |" in res.report
    assert res.prompt_tokens == 600


def test_step_cap_and_advice_stripped():
    class Looper:
        def chat(self, messages, tools=None):
            return Reply("", [ToolCall("x", "compute_metrics", '{"ticker": "KO"}')])

    res = run(["KO"], Looper(), FIX, max_steps=3, log=lambda s: None)
    assert res.stopped_reason == "max_steps" and len(res.trace) == 3

    class Adviser:
        def chat(self, messages, tools=None):
            return Reply("## Summary\nKO is steady. You should buy KO now.\n## Price performance\n## Risk\n## Fundamentals\n## Caveats")

    res = run(["KO"], Adviser(), FIX, max_repairs=0, log=lambda s: None)
    assert "should buy" not in res.report and "KO is steady." in res.report


def test_scorer_rewards_exact_numbers():
    case = {"tickers": ["KO", "PEP"]}
    n = {t: metrics_for(t, FIX).formatted["return_1y"] for t in ["KO", "PEP"]}
    llm = FakeLLM(n)
    good = run(["KO", "PEP"], llm, FIX, log=lambda s: None).report
    s = score(good, case, FIX)
    assert s["numbers"] == 1.0 and s["score"] == 100.0
    bad = good.replace(n["KO"], "+12.3%", 1).replace("## Risk", "")
    s2 = score(bad, case, FIX)
    assert s2["numbers"] < 1.0 and s2["sections"] < 1.0 and s2["score"] < 100
