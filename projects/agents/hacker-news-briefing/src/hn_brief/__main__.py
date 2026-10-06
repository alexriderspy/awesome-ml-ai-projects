import argparse
import sys
from datetime import date

from . import slack
from .brief import to_slack_text, write
from .llm import OpenAICompatible
from .pipeline import load_snapshot, run, save_snapshot
from .profile import load_profile


def main() -> None:
    ap = argparse.ArgumentParser(description="Write a personal Hacker News brief")
    ap.add_argument("--profile", required=True, help="interest profile (.yaml or .json)")
    ap.add_argument("--top", type=int, default=5, help="stories to summarize")
    ap.add_argument("--pool", type=int, default=60, help="front-page stories to consider")
    ap.add_argument("--rerank", action="store_true", help="add the LLM rerank stage")
    ap.add_argument("--comments", action="store_true", help="fetch top comments for the shortlist")
    ap.add_argument("--pages", action="store_true", help="fetch linked page text for the shortlist")
    ap.add_argument("--out", default="briefs", help="output folder (writes YYYY-MM-DD.md)")
    ap.add_argument("--snapshot", help="use a saved story JSON instead of the live API")
    ap.add_argument("--save-snapshot", help="save the fetched stories to this JSON file")
    ap.add_argument("--send-slack", action="store_true", help="also post to SLACK_WEBHOOK_URL")
    args = ap.parse_args()

    profile = load_profile(args.profile)
    stories = load_snapshot(args.snapshot) if args.snapshot else None
    client = None
    if stories is None:
        from .hn import HNClient

        client = HNClient()
        stories = client.top_stories(args.pool)
        if args.save_snapshot:
            save_snapshot(stories, args.save_snapshot)
    day = date.today()
    res = run(profile, OpenAICompatible(), client=client, stories=stories, top_k=args.top, pool=args.pool,
              rerank=args.rerank, comments=args.comments, pages=args.pages, day=day)
    for line in res.log:
        print(f"[hn_brief] {line}", file=sys.stderr)
    path = write(res.markdown, args.out, day)
    print(f"[hn_brief] wrote {path}", file=sys.stderr)

    if args.send_slack:
        slack.send(to_slack_text(res.entries, day))
        print("[hn_brief] posted to Slack", file=sys.stderr)


if __name__ == "__main__":
    main()
