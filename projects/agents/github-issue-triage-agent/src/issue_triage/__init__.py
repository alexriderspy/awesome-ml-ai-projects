import os

from .agent import TriageResult, cost_usd, triage
from .snapshot import Snapshot

__all__ = ["Snapshot", "TriageResult", "cost_usd", "triage", "default_prices"]


def default_prices() -> tuple[float, float]:
    return float(os.getenv("PRICE_IN_PER_M", "0.28")), float(os.getenv("PRICE_OUT_PER_M", "0.42"))
