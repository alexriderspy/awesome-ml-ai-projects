import argparse
import json
import sys
import textwrap

from . import Snapshot, cost_usd, default_prices, triage


def print_result(r, price_in, price_out) -> None:
    dup = f"#{r.duplicate_of}" if r.duplicate_of else "-"
    cost = cost_usd(r.prompt_tokens, r.completion_tokens, price_in, price_out)
    print(f"  labels:       {', '.join(r.labels) or '-'}")
    print(f"  duplicate of: {dup}")
    print("  draft reply:")
    print(textwrap.indent(textwrap.fill(r.reply or "(none)", 90), "    | "))
    print(f"  steps={r.steps} ({r.stopped})  tokens={r.prompt_tokens}+{r.completion_tokens}  "
          f"cost=${cost:.5f}  time={r.seconds}s")


def cmd_triage(args) -> None:
    from .llm import OpenAICompatible

    snap = Snapshot.load(args.snapshot) if args.snapshot else Snapshot.load()
    if args.all:
        numbers = snap.untriaged()[: args.limit or None]
    elif args.numbers:
        numbers = args.numbers
    else:
        sys.exit("give issue numbers or --all")
    price_in, price_out = default_prices()
    llm = OpenAICompatible()
    results = []
    for n in numbers:
        issue = snap.issues[n]
        print(f"\n=== #{n} {issue['title']}")

        def show(e):
            print(f"  [{e['step']}] {e['tool']}({json.dumps(e['args'], ensure_ascii=False)[:100]}) -> {e['result']}")

        r = triage(n, snap, llm, max_steps=args.max_steps, on_event=None if args.quiet else show)
        print_result(r, price_in, price_out)
        results.append(r)
    if len(results) > 1:
        p = sum(r.prompt_tokens for r in results)
        c = sum(r.completion_tokens for r in results)
        print(f"\n{len(results)} issues  avg tokens/issue={(p + c) / len(results):.0f}  "
              f"total cost=${cost_usd(p, c, price_in, price_out):.4f}")
    if args.out:
        with open(args.out, "w") as f:
            json.dump([r.to_dict() for r in results], f, indent=2, ensure_ascii=False)
        print(f"saved {args.out} (labels, duplicates and drafts are recorded here, nothing is sent to GitHub)")


def cmd_search(args) -> None:
    snap = Snapshot.load()
    for n, s in snap.index.search(args.query, k=args.k):
        i = snap.issues[n]
        print(f"#{n:<3} {s:5.2f}  [{i['state']}] {i['title']}  {i['labels']}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="issue_triage", description="Triage issues from a frozen snapshot")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("triage", help="run the agent")
    t.add_argument("numbers", nargs="*", type=int)
    t.add_argument("--all", action="store_true", help="every issue with no labels yet")
    t.add_argument("--limit", type=int, default=0)
    t.add_argument("--max-steps", type=int, default=10)
    t.add_argument("--out", help="write results (labels, duplicate, reply, trace, tokens) as JSON")
    t.add_argument("--snapshot", help="path to an issues.json snapshot")
    t.add_argument("--quiet", action="store_true", help="hide the tool trace")
    t.set_defaults(fn=cmd_triage)
    s = sub.add_parser("search", help="BM25 search over the snapshot (no LLM)")
    s.add_argument("query")
    s.add_argument("-k", type=int, default=5)
    s.set_defaults(fn=cmd_search)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
