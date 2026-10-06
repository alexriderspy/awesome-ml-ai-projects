from .llm import ChatModel
from .transcript import Segment, chunk

MAP_SYSTEM = """You take notes on part of a video transcript.
Each transcript line starts with a [mm:ss] timestamp.
Write 3-6 bullet points of the most important ideas in this part.
End every bullet with the timestamp where the idea starts, like [04:12].
Only use timestamps that appear in the transcript. Do not invent facts."""

REDUCE_SYSTEM = """You merge notes from consecutive parts of one video into a summary.
Output markdown with exactly these sections:

## TL;DR
Two or three sentences.

## Key points
5-8 bullets, each ending with the [mm:ss] timestamp copied from the notes.

## Chapters
One line per chapter: [mm:ss] Chapter title

Only use timestamps that appear in the notes. Keep the whole summary under {max_words} words."""


def summarize(segments: list[Segment], llm: ChatModel, max_words: int = 300, chunk_chars: int = 6000) -> str:
    if not segments:
        raise ValueError("Transcript is empty")
    parts = chunk(segments, max_chars=chunk_chars)
    notes = [llm.complete(MAP_SYSTEM, f"Transcript part {i + 1} of {len(parts)}:\n\n{p}") for i, p in enumerate(parts)]
    joined = "\n\n".join(f"Notes for part {i + 1}:\n{n}" for i, n in enumerate(notes))
    return llm.complete(REDUCE_SYSTEM.format(max_words=max_words), joined).strip()
