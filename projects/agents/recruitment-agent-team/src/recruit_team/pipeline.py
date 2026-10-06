import json
from dataclasses import asdict
from pathlib import Path

from .documents import JobDescription, Resume
from .interviewer import questions_all, questions_markdown
from .scheduler import Calendar, run_scheduler, schedule_markdown
from .screener import screen_all, shortlist_markdown

DEFAULT_CALENDAR = Path(__file__).resolve().parents[2] / "eval" / "practice" / "calendar.json"


def run_pipeline(llm, jd: JobDescription, resumes: list[Resume], calendar: Calendar | None = None,
                 max_shortlist: int = 3, threshold: float = 50.0, log=print) -> dict:
    log(f"Screening {len(resumes)} resumes for: {jd.title}")
    results = screen_all(llm, jd, resumes, max_shortlist=max_shortlist, threshold=threshold)
    shortlist = [r for r in results if r.shortlisted]
    for r in results:
        v, t = r.quotes_final
        log(f"  {r.candidate_id:12s} fit={r.fit:5.1f} qualifies={'yes' if r.qualifies else 'no ':3s} "
            f"quotes {v}/{t} valid, attempts={r.attempts}{'  <- shortlisted' if r.shortlisted else ''}")

    log(f"Writing interview questions for {len(shortlist)} shortlisted candidates")
    by_id = {r.candidate_id: r for r in resumes}
    questions = questions_all(llm, jd, by_id, shortlist)

    calendar = calendar or Calendar.load(DEFAULT_CALENDAR)
    log("Scheduling interviews")
    sched = run_scheduler(llm, calendar, [r.candidate_id for r in shortlist], panel=jd.panel, role=jd.title,
                          on_step=lambda e: log(f"  step {e['step']}: {e['tool']}({json.dumps(e['args'])}) -> {e['result']}"))
    return {"jd": jd, "results": results, "questions": questions, "schedule": sched, "calendar": calendar}


def write_outputs(out: dict, folder: str | Path) -> list[Path]:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    jd, cal, sched = out["jd"], out["calendar"], out["schedule"]
    files = {
        "shortlist.md": shortlist_markdown(jd, out["results"]),
        "shortlist.json": json.dumps({"role": jd.title, "candidates": [r.to_dict() for r in out["results"]]}, indent=2),
        "questions.md": questions_markdown(jd, out["questions"]),
        "questions.json": json.dumps(out["questions"], indent=2),
        "schedule.md": schedule_markdown(sched, cal),
        "schedule.json": json.dumps(asdict(sched), indent=2),
        "calendar-after.json": json.dumps({**cal.data, "bookings": [{k: v for k, v in b.items() if k != "new"}
                                                                    for b in cal.bookings]}, indent=2),
    }
    paths = []
    for name, text in files.items():
        p = folder / name
        p.write_text(text, encoding="utf-8")
        paths.append(p)
    return paths
