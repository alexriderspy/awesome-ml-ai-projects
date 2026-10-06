import math
import statistics
from dataclasses import dataclass, field

from .data import DataSource, PriceBar

TRADING_DAYS = 252
LOOKBACK = {"1M": 21, "6M": 126}

METRIC_LABELS = {
    "last_close": "Last close",
    "return_1m": "1M return",
    "return_6m": "6M return",
    "return_1y": "1Y return",
    "volatility": "Volatility (ann.)",
    "max_drawdown": "Max drawdown",
    "market_cap": "Market cap",
    "trailing_pe": "Trailing P/E",
    "forward_pe": "Forward P/E",
    "revenue_growth": "Revenue growth (YoY)",
    "profit_margin": "Profit margin",
    "dividend_yield": "Dividend yield",
    "beta": "Beta",
}
RANKED = ["return_1m", "return_6m", "return_1y", "volatility", "max_drawdown", "market_cap", "trailing_pe", "forward_pe", "revenue_growth", "profit_margin", "dividend_yield", "beta"]


def fmt_money(x: float) -> str:
    return f"${x:,.2f}"


def fmt_signed_pct(x: float) -> str:
    return f"{x * 100:+.1f}%"


def fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def fmt_billions(x: float) -> str:
    return f"${x / 1e9:,.1f}B"


def fmt_ratio(x: float, digits: int = 1) -> str:
    return f"{x:.{digits}f}"


NA = "n/a"


def period_return(closes: list[float], days: int | None) -> float | None:
    if len(closes) < 2:
        return None
    if days is None:
        start = closes[0]
    elif len(closes) > days:
        start = closes[-1 - days]
    else:
        return None
    return closes[-1] / start - 1


def annualized_volatility(closes: list[float]) -> float | None:
    rets = [b / a - 1 for a, b in zip(closes, closes[1:])]
    if len(rets) < 2:
        return None
    return statistics.stdev(rets) * math.sqrt(TRADING_DAYS)


def max_drawdown(closes: list[float]) -> float | None:
    if not closes:
        return None
    peak, worst = closes[0], 0.0
    for c in closes:
        peak = max(peak, c)
        worst = min(worst, c / peak - 1)
    return worst


@dataclass
class Metrics:
    ticker: str
    name: str
    currency: str
    start_date: str
    end_date: str
    raw: dict = field(default_factory=dict)
    formatted: dict = field(default_factory=dict)

    def table_row(self) -> list[str]:
        return [self.ticker] + [self.formatted[k] for k in METRIC_LABELS]


def _num(v) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def compute_metrics(ticker: str, prices: list[PriceBar], fundamentals: dict) -> Metrics:
    closes = [p.close for p in prices]
    if not closes:
        raise ValueError(f"No prices for {ticker}")
    f = fundamentals
    raw = {
        "last_close": closes[-1],
        "return_1m": period_return(closes, LOOKBACK["1M"]),
        "return_6m": period_return(closes, LOOKBACK["6M"]),
        "return_1y": period_return(closes, None),
        "volatility": annualized_volatility(closes),
        "max_drawdown": max_drawdown(closes),
        "market_cap": _num(f.get("marketCap")),
        "trailing_pe": _num(f.get("trailingPE")),
        "forward_pe": _num(f.get("forwardPE")),
        "revenue_growth": _num(f.get("revenueGrowth")),
        "profit_margin": _num(f.get("profitMargins")),
        "dividend_yield": None if _num(f.get("dividendYield")) is None else _num(f.get("dividendYield")) / 100,
        "beta": _num(f.get("beta")),
    }
    fmt = {
        "last_close": fmt_money,
        "return_1m": fmt_signed_pct, "return_6m": fmt_signed_pct, "return_1y": fmt_signed_pct,
        "volatility": fmt_pct, "max_drawdown": fmt_pct,
        "market_cap": fmt_billions,
        "trailing_pe": fmt_ratio, "forward_pe": fmt_ratio,
        "revenue_growth": fmt_signed_pct, "profit_margin": fmt_pct, "dividend_yield": fmt_pct,
        "beta": lambda x: fmt_ratio(x, 2),
    }
    formatted = {k: (NA if v is None else fmt[k](v)) for k, v in raw.items()}
    return Metrics(
        ticker=ticker.upper(),
        name=f.get("shortName") or ticker.upper(),
        currency=f.get("currency") or "USD",
        start_date=prices[0].date,
        end_date=prices[-1].date,
        raw=raw,
        formatted=formatted,
    )


def metrics_for(ticker: str, source: DataSource) -> Metrics:
    return compute_metrics(ticker, source.prices(ticker), source.fundamentals(ticker))


def comparison_table(ms: list[Metrics]) -> str:
    head = "| Metric | " + " | ".join(m.ticker for m in ms) + " |"
    sep = "|---|" + "---|" * len(ms)
    rows = [f"| {label} | " + " | ".join(m.formatted[k] for m in ms) + " |" for k, label in METRIC_LABELS.items()]
    return "\n".join([head, sep, *rows])


def rankings(ms: list[Metrics]) -> list[str]:
    lines = []
    for k in RANKED:
        have = [m for m in ms if m.raw.get(k) is not None]
        if len(have) < 2:
            continue
        hi = max(have, key=lambda m: m.raw[k])
        lo = min(have, key=lambda m: m.raw[k])
        lines.append(f"{METRIC_LABELS[k]}: highest {hi.ticker} ({hi.formatted[k]}), lowest {lo.ticker} ({lo.formatted[k]})")
    return lines
