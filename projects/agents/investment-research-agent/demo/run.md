# Demo run (live yfinance data, deepseek-flash)

Not financial advice. This is a recorded run of the agent, kept to show how it works.

```bash
PYTHONPATH=src python -m stock_research MSFT GOOGL NVDA --focus "how growth, valuation and risk differ" \
    --out demo/report-MSFT-GOOGL-NVDA.md
```

## Agent log (stderr)

The model asked for all seven tools in one turn (parallel tool calls). The loop ran each one and sent the results back, then the model wrote the narrative. The self-check found no problems, so no repair round was needed.

```
[step 1] compute_metrics({"ticker": "MSFT"}) -> {  "ticker": "MSFT",  "window": "2025-10-06 to 2026-10-05",  "Last close": "$525.18",  "1M return": "+3.0%",  "6M return...
[step 1] compute_metrics({"ticker": "GOOGL"}) -> {  "ticker": "GOOGL",  "window": "2025-10-06 to 2026-10-05",  "Last close": "$346.47",  "1M return": "+1.2%",  "6M retur...
[step 1] compute_metrics({"ticker": "NVDA"}) -> {  "ticker": "NVDA",  "window": "2025-10-06 to 2026-10-05",  "Last close": "$238.90",  "1M return": "+4.7%",  "6M return...
[step 1] get_fundamentals({"ticker": "MSFT"}) -> {  "ticker": "MSFT",  "name": "Microsoft Corporation",  "sector": "Technology",  "currency": "USD",  "Market cap": "$3,8...
[step 1] get_fundamentals({"ticker": "GOOGL"}) -> {  "ticker": "GOOGL",  "name": "Alphabet Inc.",  "sector": "Communication Services",  "currency": "USD",  "Market cap": ...
[step 1] get_fundamentals({"ticker": "NVDA"}) -> {  "ticker": "NVDA",  "name": "NVIDIA Corporation",  "sector": "Technology",  "currency": "USD",  "Market cap": "$5,768....
[step 1] compare({"tickers": ["MSFT", "GOOGL", "NVDA"]}) -> {  "table": "| Metric | MSFT | GOOGL | NVDA |\n|---|---|---|---|\n| Last close | $525.18 | $346.47 | $238.90 |\n| 1M ret...

[7 tool calls, 0 repairs, 3109+1008 tokens]
```

## Tool-call trace

| Step | Tool | Arguments | Result (start) |
|---|---|---|---|
| 1 | `compute_metrics` | `{"ticker": "MSFT"}` | {  "ticker": "MSFT",  "window": "2025-10-06 to 2026-10-05",  "Last close": "$525.18",  "1M… |
| 1 | `compute_metrics` | `{"ticker": "GOOGL"}` | {  "ticker": "GOOGL",  "window": "2025-10-06 to 2026-10-05",  "Last close": "$346.47",  "1… |
| 1 | `compute_metrics` | `{"ticker": "NVDA"}` | {  "ticker": "NVDA",  "window": "2025-10-06 to 2026-10-05",  "Last close": "$238.90",  "1M… |
| 1 | `get_fundamentals` | `{"ticker": "MSFT"}` | {  "ticker": "MSFT",  "name": "Microsoft Corporation",  "sector": "Technology",  "currency… |
| 1 | `get_fundamentals` | `{"ticker": "GOOGL"}` | {  "ticker": "GOOGL",  "name": "Alphabet Inc.",  "sector": "Communication Services",  "cur… |
| 1 | `get_fundamentals` | `{"ticker": "NVDA"}` | {  "ticker": "NVDA",  "name": "NVIDIA Corporation",  "sector": "Technology",  "currency": … |
| 1 | `compare` | `{"tickers": ["MSFT", "GOOGL", "NVDA"]}` | {  "table": "\| Metric \| MSFT \| GOOGL \| NVDA \|\n\|---\|---\|---\|---\|\n\| Last close \| $525.18 \|… |

## Final report

See [report-MSFT-GOOGL-NVDA.md](report-MSFT-GOOGL-NVDA.md).
