import json
import re
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, ValidationError

from .llm import ChatModel

MAX_BULLETS = 5
MIN_BULLETS = 3
MAX_BULLET_WORDS = 12


class OutlineSection(BaseModel):
    title: str = Field(min_length=1)
    slides: list[str] = Field(min_length=1)


class Outline(BaseModel):
    title: str = Field(min_length=1)
    subtitle: str = ""
    sections: list[OutlineSection] = Field(min_length=1)


class Slide(BaseModel):
    title: str = Field(min_length=1)
    bullets: list[str]
    notes: str = ""
    image_query: str | None = None


class SectionSlides(BaseModel):
    slides: list[Slide]


class Section(BaseModel):
    title: str
    slides: list[Slide]


class Deck(BaseModel):
    title: str
    subtitle: str = ""
    sections: list[Section]

    def content_slides(self) -> list[Slide]:
        return [s for sec in self.sections for s in sec.slides]


@dataclass
class Stats:
    calls: int = 0
    steps: int = 0
    first_try_valid: int = 0
    failed_steps: int = 0
    errors: list[str] = field(default_factory=list)


OUTLINE_SYSTEM = """You plan slide decks. Reply with JSON only, no prose, in this shape:
{"title": "...", "subtitle": "...", "sections": [{"title": "...", "slides": ["slide title", "..."]}]}
Rules:
- exactly {n} slide titles in total across all sections
- 2 to 4 sections, in a logical teaching order
- slide titles are short (at most 8 words) and specific to the topic"""

SLIDES_SYSTEM = """You write the slides for one section of a deck. Reply with JSON only, in this shape:
{"slides": [{"title": "...", "bullets": ["..."], "notes": "...", "image_query": "..."}]}
Rules:
- one slide per given title, same order, same titles
- {min_b} to {max_b} bullets per slide; every bullet at most {max_w} words, no trailing period
- bullets are concrete facts, numbers or steps, not vague claims
- notes: what the speaker says, 40-90 words
- image_query: 2-4 words for a photo or diagram search, or null if no image fits"""


def parse_json(text: str):
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found")
    return json.loads(text[start : end + 1])


def outline_problems(outline: Outline, n: int) -> list[str]:
    total = sum(len(s.slides) for s in outline.sections)
    probs = []
    if total != n:
        probs.append(f"you planned {total} slide titles, but exactly {n} are required")
    if not 2 <= len(outline.sections) <= 4 and n >= 4:
        probs.append(f"use 2 to 4 sections, not {len(outline.sections)}")
    return probs


def slide_problems(got: SectionSlides, titles: list[str]) -> list[str]:
    probs = []
    if len(got.slides) != len(titles):
        probs.append(f"return exactly {len(titles)} slides, you returned {len(got.slides)}")
    for s in got.slides:
        if not MIN_BULLETS <= len(s.bullets) <= MAX_BULLETS:
            probs.append(f"slide '{s.title}' has {len(s.bullets)} bullets; use {MIN_BULLETS}-{MAX_BULLETS}")
        for b in s.bullets:
            if len(b.split()) > MAX_BULLET_WORDS:
                probs.append(f"bullet '{b}' has {len(b.split())} words; max is {MAX_BULLET_WORDS}")
    return probs


def ask_validated(llm: ChatModel, system: str, user: str, model_cls, check, stats: Stats, retries: int = 2):
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    stats.steps += 1
    last = None
    for attempt in range(retries + 1):
        reply = chat(llm, messages)
        stats.calls += 1
        try:
            obj = model_cls.model_validate(parse_json(reply))
            probs = check(obj)
            last = obj
        except (ValueError, ValidationError) as e:
            probs = [f"invalid JSON for the schema: {str(e)[:300]}"]
        if not probs:
            stats.first_try_valid += attempt == 0
            return obj
        stats.errors.extend(probs)
        messages += [
            {"role": "assistant", "content": reply},
            {"role": "user", "content": "Fix these problems and reply with the full JSON again:\n- " + "\n- ".join(probs)},
        ]
    stats.failed_steps += 1
    return last


def chat(llm, messages: list[dict]) -> str:
    if hasattr(llm, "chat"):
        return llm.chat(messages)
    convo = "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages[1:])
    return llm.complete(messages[0]["content"], convo)


def generate_deck(topic: str, llm: ChatModel, n_slides: int = 8, audience: str = "software engineers") -> tuple[Deck, Stats]:
    stats = Stats()
    outline = ask_validated(
        llm,
        OUTLINE_SYSTEM.replace("{n}", str(n_slides)),
        f"Topic: {topic}\nAudience: {audience}\nNumber of slides: {n_slides}",
        Outline,
        lambda o: outline_problems(o, n_slides),
        stats,
    )
    if outline is None:
        raise RuntimeError("The model never returned a usable outline: " + "; ".join(stats.errors[-3:]))

    system = SLIDES_SYSTEM.replace("{min_b}", str(MIN_BULLETS)).replace("{max_b}", str(MAX_BULLETS)).replace("{max_w}", str(MAX_BULLET_WORDS))
    sections = []
    for sec in outline.sections:
        user = (
            f"Deck: {outline.title}\nAudience: {audience}\nSection: {sec.title}\n"
            "Slide titles:\n" + "\n".join(f"- {t}" for t in sec.slides)
        )
        got = ask_validated(llm, system, user, SectionSlides, lambda g, t=sec.slides: slide_problems(g, t), stats)
        slides = got.slides if got else [Slide(title=t, bullets=[]) for t in sec.slides]
        sections.append(Section(title=sec.title, slides=slides))
    return Deck(title=outline.title, subtitle=outline.subtitle, sections=sections), stats
