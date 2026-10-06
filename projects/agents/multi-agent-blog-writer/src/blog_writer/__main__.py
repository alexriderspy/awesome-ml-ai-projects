import argparse
import sys

from .llm import OpenAICompatible
from .search import httpx_fetch
from .swarm import format_event
from .team import write_post


def main() -> None:
    ap = argparse.ArgumentParser(description="Research a topic and write a cited blog post with five agents")
    ap.add_argument("topic")
    ap.add_argument("--words", type=int, default=600, help="word budget for the post body")
    ap.add_argument("--fetch", action="store_true", help="let the Researcher read full pages with httpx")
    ap.add_argument("--max-steps", type=int, default=30)
    ap.add_argument("--out", help="write the final post here")
    args = ap.parse_args()

    res = write_post(args.topic, OpenAICompatible(), word_budget=args.words, fetch=httpx_fetch if args.fetch else None,
                     max_steps=args.max_steps, on_event=lambda e: print(format_event(e), file=sys.stderr, flush=True))
    post = res.state.get("final") or res.state.get("draft") or ""
    print(f"\nstopped: {res.stopped} after {res.steps} steps, {len(res.state['sources'])} sources, "
          f"{res.state['revisions']} revision(s)\n", file=sys.stderr)
    if args.out:
        with open(args.out, "w") as f:
            f.write(post)
    print(post)


if __name__ == "__main__":
    main()
