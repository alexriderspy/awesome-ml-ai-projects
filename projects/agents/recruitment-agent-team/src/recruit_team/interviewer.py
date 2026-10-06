from concurrent.futures import ThreadPoolExecutor

from .documents import JobDescription, Resume
from .llm import ChatModel, parse_json
from .redact import redact
from .screener import ScreenResult, quote_in

SYSTEM = """You prepare a structured interview for one candidate. Write 4 to 6 questions.
Each question targets either:
- a "gap": a requirement scored 0-2, so the interview checks whether the skill is really there, or
- a "claim": a specific statement on the resume, so the interview asks for depth, numbers or trade-offs.
Ask about work and skills only. Never ask about age, family, health, origin, religion or anything personal.

Return JSON only:
{"questions": [{"type": "gap" or "claim", "requirement": "M1", "anchor": "exact words copied from the resume (claims) or \\"\\"", "question": "..."}]}"""


def build_prompt(jd: JobDescription, redacted_resume: str, screen: ScreenResult) -> str:
    reqs = {r.id: r.text for r in jd.requirements}
    scored = "\n".join(f"{i['id']} score {i['score']}/3 - {reqs[i['id']]}" + (f' | evidence: "{i["evidence"]}"'
                                                                                 if i["evidence"] else "")
                       for i in screen.items)
    return f"Job: {jd.title}\n\nScreening result:\n{scored}\n\n<resume>\n{redacted_resume}</resume>"


def questions_for(llm: ChatModel, jd: JobDescription, resume: Resume, screen: ScreenResult) -> list[dict]:
    red = redact(resume.text).text
    try:
        raw = parse_json(llm.complete(SYSTEM, build_prompt(jd, red, screen))).get("questions", [])
    except (ValueError, AttributeError):
        return []
    ids = {r.id for r in jd.requirements}
    out = []
    for q in raw if isinstance(raw, list) else []:
        text = str(q.get("question", "")).strip()
        if not text:
            continue
        anchor = str(q.get("anchor") or "").strip()
        out.append({
            "type": q.get("type") if q.get("type") in ("gap", "claim") else "gap",
            "requirement": q.get("requirement") if q.get("requirement") in ids else "",
            "anchor": anchor if anchor and quote_in(anchor, red) else "",
            "anchor_dropped": bool(anchor) and not quote_in(anchor, red),
            "question": text,
        })
    return out[:6]


def questions_all(llm: ChatModel, jd: JobDescription, resumes: dict[str, Resume],
                  shortlist: list[ScreenResult], workers: int = 4) -> dict[str, list[dict]]:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        qs = pool.map(lambda s: questions_for(llm, jd, resumes[s.candidate_id], s), shortlist)
    return {s.candidate_id: q for s, q in zip(shortlist, qs)}


def questions_markdown(jd: JobDescription, questions: dict[str, list[dict]]) -> str:
    out = [f"# Interview questions: {jd.title}"]
    for cid, qs in questions.items():
        out += ["", f"## {cid}", ""]
        for n, q in enumerate(qs, 1):
            tag = f"{q['type']}{', ' + q['requirement'] if q['requirement'] else ''}"
            out.append(f"{n}. [{tag}] {q['question']}")
            if q["anchor"]:
                out.append(f'   - resume says: "{q["anchor"]}"')
    return "\n".join(out) + "\n"
