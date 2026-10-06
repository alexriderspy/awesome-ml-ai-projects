import argparse
import json

from .agent import format_entry, run_agent
from .llm import OpenAICompatible
from .toolbox import default_tools


def main() -> None:
    ap = argparse.ArgumentParser(description="Ask a question; the model may call tools to answer it")
    ap.add_argument("question", nargs="?")
    ap.add_argument("--notes", help="notes JSON file (default: $NOTES_PATH or notes.json)")
    ap.add_argument("--max-steps", type=int, default=6)
    ap.add_argument("--schemas", action="store_true", help="print the generated tool schemas and exit")
    args = ap.parse_args()

    tools = default_tools(args.notes)
    if args.schemas:
        print(json.dumps([t.schema for t in tools], indent=2))
        return
    if not args.question:
        ap.error("question is required")

    print("Trace:")
    result = run_agent(args.question, OpenAICompatible(), tools, max_steps=args.max_steps,
                       log=lambda e: print("  " + format_entry(e)))
    if not result.trace:
        print("  (no tool calls)")
    print(f"\nAnswer ({result.steps} model call{'s' if result.steps != 1 else ''}):\n{result.answer}")


if __name__ == "__main__":
    main()
