import argparse
import json
import sys

from .extract import extract
from .llm import OpenAICompatible
from .schemas import SCHEMAS


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract validated JSON from messy text")
    ap.add_argument("schema", choices=sorted(SCHEMAS))
    ap.add_argument("file", help="text file, or - for stdin")
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--samples", type=int, default=2, help="extra samples for agreement-based confidence (0 = off)")
    args = ap.parse_args()

    text = sys.stdin.read() if args.file == "-" else open(args.file).read()
    res = extract(text, args.schema, OpenAICompatible(), retries=args.retries, samples=args.samples)
    if not res.valid:
        print("Could not get valid JSON after retries:\n" + "\n".join(res.errors), file=sys.stderr)
        sys.exit(1)
    print(json.dumps({"data": res.data, "confidence": res.confidence, "attempts": res.attempts,
                      "errors_fixed": res.errors}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
