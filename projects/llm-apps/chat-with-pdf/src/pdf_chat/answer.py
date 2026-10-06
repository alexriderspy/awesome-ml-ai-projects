import re
from dataclasses import dataclass, field

from .pdf import Chunk

NOT_FOUND = "Not in the document."

SYSTEM = f"""You answer questions about a PDF using only the numbered excerpts given.
Each excerpt starts with its page, like [p. 3].
Rules:
- answer in 1-3 sentences, then stop
- after each claim, cite the page it came from, like [p. 3]; cite only pages shown in the excerpts
- if the excerpts don't contain the answer, reply exactly: {NOT_FOUND}"""

CITE_RE = re.compile(r"\[(?:p|pp|page|pages)\.?\s*([\d,\s\-–]+)\]", re.I)


@dataclass
class Answer:
    text: str
    cited: list[int]
    sources: list[Chunk]
    bad_citations: list[int] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return NOT_FOUND.lower().rstrip(".") not in self.text.lower()


def parse_citations(text: str) -> list[int]:
    pages = []
    for group in CITE_RE.findall(text):
        for part in re.split(r"[,\s]+", group.strip()):
            if re.fullmatch(r"\d+[-–]\d+", part):
                a, b = map(int, re.split(r"[-–]", part))
                pages += list(range(a, b + 1))
            elif part.isdigit():
                pages.append(int(part))
    return sorted(set(pages))


def format_context(chunks: list[Chunk]) -> str:
    return "\n\n".join(f"[p. {c.page}] {c.text}" for c in chunks)


def answer(question: str, retriever, llm, k: int = 4) -> Answer:
    chunks = retriever.search(question, k=k)
    if not chunks:
        return Answer(NOT_FOUND, [], [])
    text = llm.complete(SYSTEM, f"Excerpts:\n\n{format_context(chunks)}\n\nQuestion: {question}").strip()
    cited = parse_citations(text)
    retrieved = {c.page for c in chunks}
    return Answer(text, cited, chunks, [p for p in cited if p not in retrieved])
