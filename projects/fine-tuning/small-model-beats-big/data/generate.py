import argparse
import json
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ticket_router.labels import CATEGORIES, category_block
from ticket_router.llm import OpenAICompatible

STYLES = [
    "short and terse, often one line, some typos and no punctuation",
    "polite and detailed, 3-5 sentences, mentions plan names and dates",
    "angry or frustrated, may use caps, threatens to leave or demands a manager",
    "non-native English speakers, simple grammar, mixed formality",
    "ambiguous: mentions a second topic in passing, but the main ask clearly belongs to the target category",
]

PERSONAS = "freelancers, small shop owners, accountants, startup founders, office managers, developers using the API"

SYSTEM = "You write realistic customer support tickets for testing a ticket router. Output JSON only."

PROMPT = """Product: Tallyo, an online invoicing and bookkeeping app for small businesses.
Routing categories:
{cats}

Write {n} different support tickets that a human agent would route to "{label}".
Writers: {personas}. Style for this batch: {style}.
Vary the opening words, details, product areas and length. Don't name the category in the text.
Return a JSON object: {{"tickets": ["...", "..."]}}"""


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def gen_batch(llm, label: str, style: str, n: int) -> list[dict]:
    user = PROMPT.format(cats=category_block(), n=n, label=label, personas=PERSONAS, style=style)
    raw = llm.chat(SYSTEM, user, response_format={"type": "json_object"}).text
    try:
        tickets = json.loads(raw)["tickets"]
    except (json.JSONDecodeError, KeyError, TypeError):
        print(f"bad batch for {label}", file=sys.stderr)
        return []
    return [{"text": t.strip(), "label": label, "style": style.split(":")[0].split(",")[0]} for t in tickets if isinstance(t, str) and t.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-batch", type=int, default=20)
    ap.add_argument("--batches", type=int, default=5)
    ap.add_argument("--out", default=str(ROOT / "data" / "tickets.jsonl"))
    args = ap.parse_args()

    llm = OpenAICompatible(temperature=1.0)
    jobs = [(lab, STYLES[i % len(STYLES)]) for lab in CATEGORIES for i in range(args.batches)]
    with ThreadPoolExecutor(8) as ex:
        batches = list(ex.map(lambda j: gen_batch(llm, j[0], j[1], args.per_batch), jobs))

    seen, rows = set(), []
    for batch in batches:
        for row in batch:
            key = norm(row["text"])
            if key and key not in seen:
                seen.add(key)
                rows.append(row)
    random.Random(0).shuffle(rows)
    for i, r in enumerate(rows):
        r["id"] = f"t{i:04d}"
    with open(args.out, "w") as f:
        for r in rows:
            f.write(json.dumps({"id": r["id"], "text": r["text"], "label": r["label"], "style": r["style"]}) + "\n")
    print(f"wrote {len(rows)} tickets to {args.out}")


if __name__ == "__main__":
    main()
