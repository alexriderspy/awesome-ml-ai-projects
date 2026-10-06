import argparse
import json
from pathlib import Path

from .agent import run_agent
from .llm import OpenAICompatible


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract structured records from a web page with an LLM agent")
    ap.add_argument("url")
    ap.add_argument("description", help='what to extract, e.g. "all product names and prices"')
    ap.add_argument("--schema", help="JSON Schema file for one record (generated from the description if omitted)")
    ap.add_argument("--max-pages", type=int, default=5)
    ap.add_argument("--max-steps", type=int, default=20)
    ap.add_argument("--out", help="write records to this JSON file")
    args = ap.parse_args()

    schema = json.loads(Path(args.schema).read_text()) if args.schema else None
    res = run_agent(args.url, args.description, OpenAICompatible(), schema=schema,
                    max_pages=args.max_pages, max_steps=args.max_steps, verbose=True)
    print(f"\nschema: {json.dumps(res.schema)}")
    print(f"pages fetched: {len(res.pages)} | steps: {res.steps} | stop: {res.stop_reason} | records: {len(res.records)}")
    print(json.dumps(res.records, indent=2, ensure_ascii=False))
    if args.out:
        Path(args.out).write_text(json.dumps(res.records, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
