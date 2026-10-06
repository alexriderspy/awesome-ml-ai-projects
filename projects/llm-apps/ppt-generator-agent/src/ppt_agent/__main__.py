import argparse
import json
from pathlib import Path

from .build import build_pptx
from .llm import OpenAICompatible
from .plan import generate_deck


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate a .pptx deck from a topic")
    ap.add_argument("topic")
    ap.add_argument("--slides", type=int, default=8, help="number of content slides")
    ap.add_argument("--audience", default="software engineers")
    ap.add_argument("--out", default="deck.pptx")
    ap.add_argument("--images", action="store_true", help="add Wikimedia Commons images")
    ap.add_argument("--previews", help="folder for PNG previews of the first slides")
    ap.add_argument("--save-json", help="also save the deck content as JSON")
    args = ap.parse_args()

    deck, stats = generate_deck(args.topic, OpenAICompatible(), n_slides=args.slides, audience=args.audience)
    images = {}
    if args.images:
        from .images import fetch_images

        images = fetch_images(deck, Path(args.out).with_suffix("").as_posix() + "_images")
    out = build_pptx(deck, args.out, images)
    print(f"saved {out}  ({len(deck.content_slides())} content slides, {len(images)} images, "
          f"{stats.calls} LLM calls, {stats.first_try_valid}/{stats.steps} steps valid on first try)")
    if args.save_json:
        Path(args.save_json).write_text(json.dumps(deck.model_dump(), indent=2))
    if args.previews:
        from .render import render_previews

        paths, how = render_previews(out, deck, args.previews, pages=[0, 1, 2, 3])
        print(f"previews ({how}): " + ", ".join(str(p) for p in paths))


if __name__ == "__main__":
    main()
