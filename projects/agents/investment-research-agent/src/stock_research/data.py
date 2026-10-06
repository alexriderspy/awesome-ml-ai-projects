import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

FUNDAMENTAL_KEYS = [
    "shortName", "sector", "currency", "marketCap", "trailingPE", "forwardPE",
    "revenueGrowth", "profitMargins", "dividendYield", "beta", "totalRevenue",
]


@dataclass
class PriceBar:
    date: str
    close: float


class DataSource(Protocol):
    def prices(self, ticker: str) -> list[PriceBar]: ...
    def fundamentals(self, ticker: str) -> dict: ...


class YFinanceSource:

    def __init__(self, period: str = "1y"):
        self.period = period

    def prices(self, ticker: str) -> list[PriceBar]:
        import yfinance as yf

        hist = yf.Ticker(ticker).history(period=self.period, auto_adjust=True)
        if hist.empty:
            raise ValueError(f"No price data for {ticker!r}")
        return [PriceBar(idx.strftime("%Y-%m-%d"), float(row["Close"])) for idx, row in hist.iterrows()]

    def fundamentals(self, ticker: str) -> dict:
        import yfinance as yf

        info = yf.Ticker(ticker).info or {}
        return {k: info.get(k) for k in FUNDAMENTAL_KEYS}


class FixtureSource:

    def __init__(self, folder: str | Path):
        self.folder = Path(folder)

    def prices(self, ticker: str) -> list[PriceBar]:
        path = self.folder / f"{ticker.upper()}.csv"
        if not path.exists():
            raise ValueError(f"No fixture for {ticker!r}")
        with path.open() as f:
            return [PriceBar(r["date"], float(r["close"])) for r in csv.DictReader(f)]

    def fundamentals(self, ticker: str) -> dict:
        path = self.folder / f"{ticker.upper()}.json"
        if not path.exists():
            raise ValueError(f"No fixture for {ticker!r}")
        return json.loads(path.read_text())


def record(tickers: list[str], folder: str | Path, source: DataSource | None = None) -> None:
    source = source or YFinanceSource()
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for t in tickers:
        t = t.upper()
        with (folder / f"{t}.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "close"])
            for bar in source.prices(t):
                w.writerow([bar.date, f"{bar.close:.4f}"])
        (folder / f"{t}.json").write_text(json.dumps(source.fundamentals(t), indent=1))
