import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field

from .documents import JobDescription, Resume
from .llm import ChatModel, parse_json
from .redact import redact

SYSTEM = """You screen resumes against a job's requirements. Judge only skills and experience.
Placeholders like [CANDIDATE], [YEAR], [AGE], [EMAIL], [GENDER], [FAMILY] hide personal details on purpose; ignore them.

For every requirement id give:
- score: 0 = no evidence, 1 = related but weaker than asked, 2 = meets it, 3 = clearly exceeds it
- evidence: one exact span copied character for character from the resume (5-30 words) that supports the score.
  Do not paraphrase, fix typos, add "..." or join text from different lines. Use "" when score is 0.

Return JSON only:
{"requirements": [{"id": "M1", "score": 2, "evidence": "exact words from the resume"}], "summary": "one neutral sentence"}"""

MUST_WEIGHT, NICE_WEIGHT = 2, 1


def _norm(s: str) -> str:
    s = s.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", s).strip()


def quote_in(quote: str, source: str) -> bool:
    q = _norm(quote).strip('"').strip()
    return bool(q) and q in _norm(source)


@dataclass
class ScreenResult:
    candidate_id: str
    items: list[dict] = field(default_factory=list)
    summary: str = ""
    fit: float = 0.0
    qualifies: bool = False
    shortlisted: bool = False
    attempts: int = 0
    quotes_first: tuple[int, int] = (0, 0)
    quotes_final: tuple[int, int] = (0, 0)
    redactions: dict = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def build_prompt(jd: JobDescription, redacted_resume: str) -> str:
    return (f"Job: {jd.title}\n\nRequirements:\n{jd.requirement_lines()}\n\n"
            f"<resume>\n{redacted_resume}</resume>")


def check(reply: dict, jd: JobDescription, resume_text: str) -> tuple[list[dict], list[str]]:
    ids = {r.id for r in jd.requirements}
    raw = reply.get("requirements") if isinstance(reply, dict) else None
    if not isinstance(raw, list):
        return [], ['Reply must be a JSON object with a "requirements" list.']
    items, problems, seen = [], [], set()
    for it in raw:
        rid = str(it.get("id", "")).strip()
        if rid not in ids or rid in seen:
            problems.append(f"Unknown or repeated requirement id {rid!r}.")
            continue
        seen.add(rid)
        try:
            score = max(0, min(3, int(it.get("score", 0))))
        except (TypeError, ValueError):
            score = 0
        ev = str(it.get("evidence") or "").strip()
        valid = score == 0 or quote_in(ev, resume_text)
        if score > 0 and not ev:
            problems.append(f"{rid}: score {score} needs an evidence quote.")
        elif not valid:
            problems.append(f"{rid}: evidence {ev!r} is not an exact span of the resume.")
        items.append({"id": rid, "score": score, "evidence": ev, "valid": valid})
    for rid in sorted(ids - seen):
        problems.append(f"{rid}: missing.")
    return items, problems


def _quote_stats(items: list[dict]) -> tuple[int, int]:
    quoted = [i for i in items if i["score"] > 0]
    return sum(i["valid"] for i in quoted), len(quoted)


def fit_score(items: list[dict], jd: JobDescription) -> float:
    weight = {r.id: MUST_WEIGHT if r.must else NICE_WEIGHT for r in jd.requirements}
    got = sum(weight[i["id"]] * i["score"] for i in items)
    return round(100 * got / (3 * sum(weight.values())), 1)


def screen_one(llm: ChatModel, jd: JobDescription, resume: Resume, min_must: int = 2) -> ScreenResult:
    red = redact(resume.text)
    res = ScreenResult(resume.candidate_id, redactions=dict(red.counts))
    prompt = build_prompt(jd, red.text)
    items: list[dict] = []
    for attempt in (1, 2):
        res.attempts = attempt
        reply_text = llm.complete(SYSTEM, prompt)
        try:
            reply = parse_json(reply_text)
        except ValueError:
            reply, items, problems = {}, [], ["Reply was not valid JSON."]
        else:
            items, problems = check(reply, jd, red.text)
        stats = _quote_stats(items)
        if attempt == 1:
            res.quotes_first = stats
        res.quotes_final = stats
        res.summary = str(reply.get("summary", "")) if isinstance(reply, dict) else ""
        if not problems:
            break
        prompt = (f"{build_prompt(jd, red.text)}\n\nYour previous answer:\n{reply_text}\n\n"
                  "Fix these problems and answer again with the full JSON. Evidence must be copied exactly "
                  "from the resume:\n- " + "\n- ".join(problems))
    else:
        res.error = "; ".join(problems)[:500]

    for it in items:
        if it["score"] > 0 and not it["valid"]:
            it["flag"] = "dropped: quote not found in resume"
            it["score"], it["evidence"] = 0, ""
    have = {i["id"] for i in items}
    items += [{"id": r.id, "score": 0, "evidence": "", "valid": True, "flag": "missing"}
              for r in jd.requirements if r.id not in have]
    order = {r.id: n for n, r in enumerate(jd.requirements)}
    res.items = sorted(items, key=lambda i: order[i["id"]])
    res.fit = fit_score(res.items, jd)
    musts = {r.id for r in jd.requirements if r.must}
    res.qualifies = all(i["score"] >= min_must for i in res.items if i["id"] in musts)
    return res


def screen_all(llm: ChatModel, jd: JobDescription, resumes: list[Resume], max_shortlist: int = 3,
               threshold: float = 50.0, workers: int = 6) -> list[ScreenResult]:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda r: screen_one(llm, jd, r), resumes))
    results.sort(key=lambda r: (-r.fit, r.candidate_id))
    picked = [r for r in results if r.qualifies and r.fit >= threshold][:max_shortlist]
    for r in picked:
        r.shortlisted = True
    return results


def shortlist_markdown(jd: JobDescription, results: list[ScreenResult]) -> str:
    reqs = {r.id: r for r in jd.requirements}
    out = [f"# Shortlist: {jd.title}", "", "| Rank | Candidate | Fit | All must-haves met | Shortlisted |",
           "|---|---|---|---|---|"]
    for n, r in enumerate(results, 1):
        out.append(f"| {n} | {r.candidate_id} | {r.fit} | {'yes' if r.qualifies else 'no'} | "
                   f"{'**yes**' if r.shortlisted else 'no'} |")
    for r in results:
        out += ["", f"## {r.candidate_id} (fit {r.fit})", "", r.summary, ""]
        for it in r.items:
            ev = f' "{it["evidence"]}"' if it["evidence"] else ""
            flag = f" ({it['flag']})" if it.get("flag") else ""
            out.append(f"- **{it['id']}** {it['score']}/3 {reqs[it['id']].text}:{ev}{flag}")
        if r.redactions:
            out.append(f"- redacted before screening: {json.dumps(r.redactions, sort_keys=True)}")
    return "\n".join(out) + "\n"
