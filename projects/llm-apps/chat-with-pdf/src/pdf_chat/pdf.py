import io
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Chunk:
    id: int
    page: int
    text: str


def load_pages(src: str | Path | bytes) -> list[str]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(src) if isinstance(src, bytes) else str(src))
    return [re.sub(r"[ \t]+", " ", p.extract_text() or "").strip() for p in reader.pages]


def chunk_pages(pages: list[str], size: int = 700, overlap: int = 150) -> list[Chunk]:
    chunks = []
    for page_no, text in enumerate(pages, 1):
        sentences = re.split(r"(?<=[.!?])\s+|\n{2,}", text)
        buf = ""
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            if buf and len(buf) + len(s) > size:
                chunks.append(Chunk(len(chunks), page_no, buf.strip()))
                buf = buf[-overlap:].split(" ", 1)[-1] if overlap else ""
            buf += " " + s
        if buf.strip():
            chunks.append(Chunk(len(chunks), page_no, buf.strip()))
    return chunks
