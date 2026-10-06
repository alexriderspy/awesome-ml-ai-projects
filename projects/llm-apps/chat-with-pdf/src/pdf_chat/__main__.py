import argparse

from .answer import answer
from .llm import OpenAICompatible
from .pdf import chunk_pages, load_pages
from .retrieve import make_retriever


def main() -> None:
    ap = argparse.ArgumentParser(description="Ask questions about a PDF; answers cite pages")
    ap.add_argument("pdf")
    ap.add_argument("questions", nargs="*", help="questions; omit for an interactive prompt")
    ap.add_argument("--retriever", choices=["auto", "bm25", "embeddings", "hybrid"], default="auto")
    ap.add_argument("-k", type=int, default=4, help="chunks to retrieve")
    args = ap.parse_args()

    chunks = chunk_pages(load_pages(args.pdf))
    retriever = make_retriever(chunks, args.retriever)
    llm = OpenAICompatible()
    print(f"{len(chunks)} chunks, retriever: {retriever.name}\n")

    def ask(q):
        a = answer(q, retriever, llm, k=args.k)
        print(f"Q: {q}\nA: {a.text}")
        if a.bad_citations:
            print(f"   warning: cited pages not in the retrieved excerpts: {a.bad_citations}")
        print()

    for q in args.questions:
        ask(q)
    if not args.questions:
        while (q := input("question> ").strip()):
            ask(q)


if __name__ == "__main__":
    main()
