import json
from typing import Callable

from .data import DataSource
from .metrics import (METRIC_LABELS, Metrics, comparison_table, fmt_money, metrics_for, rankings)


def price_summary(ticker: str, source: DataSource) -> dict:
    bars = source.prices(ticker)
    closes = [b.close for b in bars]
    hi = max(bars, key=lambda b: b.close)
    lo = min(bars, key=lambda b: b.close)
    return {
        "ticker": ticker.upper(),
        "from": bars[0].date,
        "to": bars[-1].date,
        "trading_days": len(bars),
        "first_close": fmt_money(closes[0]),
        "last_close": fmt_money(closes[-1]),
        "period_high": f"{fmt_money(hi.close)} on {hi.date}",
        "period_low": f"{fmt_money(lo.close)} on {lo.date}",
    }


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_price_history",
            "description": "Summary of the last year of daily closing prices for one ticker: date range, first/last close, high and low.",
            "parameters": {
                "type": "object",
                "properties": {"ticker": {"type": "string", "description": "Stock ticker, e.g. MSFT"}},
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fundamentals",
            "description": "Company name, sector and basic fundamentals (market cap, P/E, revenue growth, margins, dividend yield, beta), already formatted.",
            "parameters": {
                "type": "object",
                "properties": {"ticker": {"type": "string"}},
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_metrics",
            "description": "Return, volatility and drawdown metrics for one ticker, computed in code from daily closes.",
            "parameters": {
                "type": "object",
                "properties": {"ticker": {"type": "string"}},
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare",
            "description": "Side-by-side table of all metrics for several tickers, plus which ticker is highest/lowest on each metric.",
            "parameters": {
                "type": "object",
                "properties": {"tickers": {"type": "array", "items": {"type": "string"}, "minItems": 2}},
                "required": ["tickers"],
            },
        },
    },
]


class Toolbox:

    def __init__(self, source: DataSource):
        self.source = source
        self._metrics: dict[str, Metrics] = {}

    def metrics(self, ticker: str) -> Metrics:
        t = ticker.upper().strip()
        if t not in self._metrics:
            self._metrics[t] = metrics_for(t, self.source)
        return self._metrics[t]

    def get_price_history(self, ticker: str) -> dict:
        return price_summary(ticker.upper().strip(), self.source)

    def get_fundamentals(self, ticker: str) -> dict:
        m = self.metrics(ticker)
        f = self.source.fundamentals(m.ticker)
        out = {"ticker": m.ticker, "name": m.name, "sector": f.get("sector") or "n/a", "currency": m.currency}
        for k in ["market_cap", "trailing_pe", "forward_pe", "revenue_growth", "profit_margin", "dividend_yield", "beta"]:
            out[METRIC_LABELS[k]] = m.formatted[k]
        return out

    def compute_metrics(self, ticker: str) -> dict:
        m = self.metrics(ticker)
        out = {"ticker": m.ticker, "window": f"{m.start_date} to {m.end_date}"}
        for k in ["last_close", "return_1m", "return_6m", "return_1y", "volatility", "max_drawdown"]:
            out[METRIC_LABELS[k]] = m.formatted[k]
        return out

    def compare(self, tickers: list[str]) -> dict:
        ms = [self.metrics(t) for t in tickers]
        return {"table": comparison_table(ms), "rankings": rankings(ms)}

    def functions(self) -> dict[str, Callable]:
        return {
            "get_price_history": self.get_price_history,
            "get_fundamentals": self.get_fundamentals,
            "compute_metrics": self.compute_metrics,
            "compare": self.compare,
        }

    def call(self, name: str, arguments: str) -> str:
        fn = self.functions().get(name)
        if fn is None:
            return f"ERROR: unknown tool {name!r}"
        try:
            args = json.loads(arguments or "{}")
            if not isinstance(args, dict):
                raise ValueError("arguments must be a JSON object")
        except (json.JSONDecodeError, ValueError) as e:
            return f"ERROR: bad arguments: {e}"
        try:
            return json.dumps(fn(**args), indent=1)
        except TypeError as e:
            return f"ERROR: wrong arguments for {name}: {e}"
        except Exception as e:
            return f"ERROR: {type(e).__name__}: {e}"
