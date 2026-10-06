import argparse

from .llm import OpenAICompatible
from .summarize import summarize
from .transcript import fetch_transcript


def main() -> None:
    ap = argparse.ArgumentParser(description="Summarize a YouTube video with an LLM")
    ap.add_argument("url", help="YouTube URL or 11-character video id")
    ap.add_argument("--max-words", type=int, default=300)
    args = ap.parse_args()

    segments = fetch_transcript(args.url)
    print(summarize(segments, OpenAICompatible(), max_words=args.max_words))


if __name__ == "__main__":
    main()
