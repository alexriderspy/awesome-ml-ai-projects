import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pdf_chat.answer import Answer, answer
from pdf_chat.pdf import chunk_pages, load_pages
from pdf_chat.retrieve import make_retriever

PRACTICE = Path(__file__).parent / "practice"


def score(a: Answer, case: dict) -> dict:
    gold_pages = set(case["pages"])
    text = a.text.lower()
    if not gold_pages:
        acc = float(not a.found)
        cite = float(not a.cited)
    else:
        acc = float(a.found and all(any(k in text for k in group) for group in case["keywords"]))
        cite = len(set(a.cited) & gold_pages) / len(a.cited) if a.cited else 0.0
    return {"accuracy": acc, "citation": cite, "score": round(100 * (0.6 * acc + 0.4 * cite), 1),
            "retrieved": bool(gold_pages & {c.page for c in a.sources}) if gold_pages else None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--retriever", default="auto", choices=["auto", "bm25", "embeddings", "hybrid"])
    ap.add_argument("-k", type=int, default=4)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    from pdf_chat.llm import OpenAICompatible

    spec = json.loads((PRACTICE / "qa.json").read_text())
    retriever = make_retriever(chunk_pages(load_pages(PRACTICE / spec["pdf"])), args.retriever)
    llm = OpenAICompatible()
    rows = []
    for case in spec["questions"]:
        a = answer(case["q"], retriever, llm, k=args.k)
        rows.append({"q": case["q"], "answer": a.text, "cited": a.cited, **score(a, case)})

    overall = round(sum(r["score"] for r in rows) / len(rows), 1)
    if args.json:
        print(json.dumps({"overall": overall, "model": llm.model, "retriever": retriever.name, "rows": rows}, indent=2))
        return
    for r in rows:
        print(f"score={r['score']:5.1f}  acc={r['accuracy']:.0f}  cite={r['citation']:.2f}  pages={r['cited']}  {r['q']}")
    answerable = [r for r in rows if r["retrieved"] is not None]
    print(f"\nmodel: {llm.model}   retriever: {retriever.name}   k={args.k}")
    print(f"answer accuracy: {sum(r['accuracy'] for r in rows) / len(rows):.2f}   "
          f"citation correctness: {sum(r['citation'] for r in rows) / len(rows):.2f}   "
          f"retrieval recall@{args.k}: {sum(r['retrieved'] for r in answerable) / len(answerable):.2f}")
    print(f"OVERALL {overall}/100")


if __name__ == "__main__":
    main()
