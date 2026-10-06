import argparse
import sys
from pathlib import Path

from .agent import run, trace_markdown
from .data import FixtureSource, YFinanceSource, record


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "record":
        ap = argparse.ArgumentParser(prog="stock_research record")
        ap.add_argument("tickers", nargs="+")
        ap.add_argument("--to", required=True)
        args = ap.parse_args(sys.argv[2:])
        record(args.tickers, args.to)
        print(f"saved {len(args.tickers)} tickers to {args.to}")
        return

    ap = argparse.ArgumentParser(description="Compare stocks with an LLM agent. Not financial advice.")
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--focus", default="", help="optional angle, e.g. 'risk' or 'dividends'")
    ap.add_argument("--fixtures", help="read saved data from this folder instead of yfinance")
    ap.add_argument("--out", help="write the report here")
    ap.add_argument("--trace", help="write the tool-call trace (markdown) here")
    args = ap.parse_args()

    from .llm import OpenAICompatible

    source = FixtureSource(args.fixtures) if args.fixtures else YFinanceSource()
    res = run(args.tickers, OpenAICompatible(), source, request=args.focus, log=lambda s: print(s, file=sys.stderr))
    if args.out:
        Path(args.out).write_text(res.report)
    if args.trace:
        Path(args.trace).write_text(trace_markdown(res))
    print(res.report)
    print(f"\n[{len(res.trace)} tool calls, {res.repairs} repairs, {res.prompt_tokens}+{res.completion_tokens} tokens]", file=sys.stderr)


if __name__ == "__main__":
    main()
