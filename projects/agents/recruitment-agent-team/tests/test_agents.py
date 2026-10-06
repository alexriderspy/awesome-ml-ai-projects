import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "tests"))

from fakes import FakeLLM, PipelineFake, ScriptedChat
from recruit_team.documents import Resume, load_jd, load_resumes, parse_jd
from recruit_team.interviewer import questions_for
from recruit_team.pipeline import run_pipeline, write_outputs
from recruit_team.scheduler import Calendar, run_scheduler
from recruit_team.screener import check, fit_score, quote_in, screen_all, screen_one
from run_eval import prf, schedule_score

PRACTICE = ROOT / "eval" / "practice"
JD = load_jd(PRACTICE / "backend-engineer" / "jd.md")


def cal() -> Calendar:
    return Calendar.load(PRACTICE / "calendar.json")


def test_parse_jd_sections():
    jd = parse_jd("# Role\nPanel: Data\n## About\n- ignored\n## Requirements\n- SQL\n- Python\n## Bonus\n* dbt\n")
    assert [(r.id, r.text, r.must) for r in jd.requirements] == [("M1", "SQL", True), ("M2", "Python", True),
                                                                   ("N1", "dbt", False)]
    assert jd.title == "Role" and jd.panel == "data"


def test_parse_jd_without_requirements_fails():
    with pytest.raises(ValueError):
        parse_jd("# Role\nJust prose.")


def test_practice_cases_are_complete():
    for case in sorted(p for p in PRACTICE.iterdir() if p.is_dir()):
        gold = json.loads((case / "gold.json").read_text())["shortlist"]
        ids = {r.candidate_id for r in load_resumes(case / "resumes")}
        assert 6 <= len(ids) <= 8 and set(gold) <= ids
        assert load_jd(case / "jd.md").panel


def test_quote_in_is_verbatim_up_to_whitespace():
    src = "Built the   checkout API\nin Go."
    assert quote_in("Built the checkout API in Go.", src)
    assert quote_in("“checkout API”", 'the "checkout API" in')
    assert not quote_in("Built the checkout service", src)
    assert not quote_in("", src)


def test_check_flags_bad_quotes_and_missing_ids():
    reply = {"requirements": [{"id": "M1", "score": 3, "evidence": "not in resume"},
                              {"id": "M2", "score": 2, "evidence": "Designed MySQL"},
                              {"id": "ZZ", "score": 1, "evidence": "x"}]}
    items, problems = check(reply, JD, "Designed MySQL schemas")
    assert [i["valid"] for i in items] == [False, True]
    assert any("M1" in p and "exact span" in p for p in problems)
    assert any("ZZ" in p for p in problems) and any("M3: missing" in p for p in problems)


def test_retry_with_feedback_fixes_bad_quote():
    llm = FakeLLM(bad_first=1)
    res = screen_one(llm, JD, Resume("x", "Pat Lee\n- Built Go services for five years.\n"))
    assert res.attempts == 2 and res.quotes_first == (0, 7) and res.quotes_final == (7, 7)
    assert "Your previous answer" in llm.prompts[1][1] and "not an exact span" in llm.prompts[1][1]
    assert all(i["score"] == 2 for i in res.items) and not res.error


def test_unfixed_bad_quotes_are_dropped_to_zero():
    llm = FakeLLM(bad_first=2)
    res = screen_one(llm, JD, Resume("x", "Pat Lee\n- Built Go services.\n"))
    assert res.attempts == 2 and res.quotes_final == (0, 7) and res.fit == 0 and not res.qualifies
    assert all(i["flag"].startswith("dropped") for i in res.items) and res.error


def test_fit_and_must_have_gate():
    items = [{"id": r.id, "score": 3 if r.must else 0} for r in JD.requirements]
    assert fit_score(items, JD) == round(100 * 8 * 3 / (3 * 11), 1)
    llm = FakeLLM(scores={"weak": 1, "strong": 3})
    res = screen_all(llm, JD, [Resume("a", "- strong backend\n"), Resume("b", "- weak backend\n"),
                               Resume("c", "- ok backend\n")], max_shortlist=1)
    assert [r.candidate_id for r in res] == ["a", "c", "b"]
    assert [r.shortlisted for r in res] == [True, False, False]
    assert res[1].qualifies and not res[2].qualifies


@pytest.mark.parametrize("case", ["backend-engineer", "data-analyst", "support-lead"])
def test_counterfactual_prompts_are_identical(case):
    jd = load_jd(PRACTICE / case / "jd.md")
    for twin in (PRACTICE / case / "counterfactual").glob("*.md"):
        orig = (PRACTICE / case / "resumes" / twin.name).read_text()
        a, b = FakeLLM(), FakeLLM()
        ra = screen_one(a, jd, Resume(twin.stem, orig))
        rb = screen_one(b, jd, Resume(twin.stem, twin.read_text()))
        assert a.prompts == b.prompts and ra.fit == rb.fit
        qa, qb = FakeLLM(), FakeLLM()
        questions_for(qa, jd, Resume(twin.stem, orig), ra)
        questions_for(qb, jd, Resume(twin.stem, twin.read_text()), rb)
        assert qa.prompts == qb.prompts


def test_no_raw_personal_details_reach_the_model():
    llm = FakeLLM()
    screen_all(llm, JD, load_resumes(PRACTICE / "backend-engineer" / "resumes"))
    sent = "\n".join(u for _, u in llm.prompts)
    for leak in ("Priya", "Tomasz", "Wierzbicki", "Aisha", "Date of Birth", "Age:", "Gender:", "@", "father",
                 "Women Who Code", "she/her", "Nationality"):
        assert leak not in sent, leak


def test_interviewer_keeps_real_anchors_only():
    llm = FakeLLM()
    resume = Resume("x", "Pat Lee\n- Built Go services for five years.\n")
    qs = questions_for(llm, JD, resume, screen_one(FakeLLM(), JD, resume))
    assert qs[0]["anchor"] == "Built Go services for five years." and qs[0]["type"] == "claim"
    assert qs[1]["anchor"] == "" and qs[1]["anchor_dropped"]


def test_free_slots_skip_existing_bookings():
    c = cal()
    assert c.free_slots("iv-ana") == ["2026-10-14T15:00", "2026-10-14T15:15"]
    assert "2026-10-13T11:15" in c.free_slots("iv-chen") and "2026-10-13T10:30" not in c.free_slots("iv-chen")


def test_book_slot_guards():
    c = cal()
    assert "double booking" in c.book("iv-ana", "x", "2026-10-12T09:00")["error"]
    assert "not available" in c.book("iv-ana", "x", "2026-10-12T13:00")["error"]
    assert "panel" in c.book("iv-chen", "x", "2026-10-13T11:15", panel="backend")["error"]
    assert "shortlist" in c.book("iv-ana", "y", "2026-10-14T15:00", allowed={"x"})["error"]
    assert "bad start" in c.book("iv-ana", "x", "tomorrow")["error"]
    assert c.book("iv-ben", "x", "2026-10-13T09:00")["ok"]
    assert "double booking" in c.book("iv-ben", "z", "2026-10-13T09:30")["error"]
    assert "already has" in c.book("iv-ben", "x", "2026-10-13T09:45")["error"]
    assert c.conflicts() == []


def test_agent_loop_logs_calls_recovers_and_finishes():
    turns = [
        [("list_interviewers", {"panel": "backend"})],
        [("list_free_slots", {"interviewer_id": "iv-ben", "date": "2026-10-13"})],
        [("book_slot", {"interviewer_id": "iv-ben", "candidate_id": "a", "start": "2026-10-13T09:00"}),
         ("book_slot", {"interviewer_id": "iv-ben", "candidate_id": "b", "start": "2026-10-13T09:15"})],
        [("book_slot", {"interviewer_id": "iv-ben", "candidate_id": "b", "start": "2026-10-13T09:45"})],
        [("finish", {"notes": "all booked"})],
    ]
    llm, c = ScriptedChat(turns), cal()
    run = run_scheduler(llm, c, ["a", "b"], panel="backend")
    assert run.finished and run.unscheduled == [] and run.steps == 5
    assert [e["tool"] for e in run.log] == ["list_interviewers", "list_free_slots", "book_slot", "book_slot",
                                             "book_slot", "finish"]
    assert "double booking" in run.log[3]["result"]
    assert {b["candidate"]: b["start"] for b in run.bookings} == {"a": "2026-10-13T09:00", "b": "2026-10-13T09:45"}
    tool_msgs = [m for m in llm.seen[-1] if m["role"] == "tool"]
    assert len(tool_msgs) == 5 and c.conflicts() == []
    assert schedule_score(c, ["a", "b"], "backend") == 1.0


def test_agent_loop_respects_step_cap():
    llm = ScriptedChat([[("list_interviewers", {})]] * 50)
    run = run_scheduler(llm, cal(), ["a"], max_steps=4)
    assert run.steps == 4 and not run.finished and run.unscheduled == ["a"] and len(run.log) == 4


def test_nudges_model_that_stops_early():
    llm = ScriptedChat([[], [("book_slot", {"interviewer_id": "iv-eli", "candidate_id": "a",
                                            "start": "2026-10-14T09:00"})]])
    run = run_scheduler(llm, cal(), ["a"])
    assert run.finished and run.bookings and "not booked yet" in llm.seen[1][-1]["content"]


def test_pipeline_end_to_end_writes_files(tmp_path):
    turns = [[("book_slot", {"interviewer_id": "iv-ben", "candidate_id": "be-01", "start": "2026-10-13T09:00"}),
              ("book_slot", {"interviewer_id": "iv-ana", "candidate_id": "be-02", "start": "2026-10-14T15:00"}),
              ("book_slot", {"interviewer_id": "iv-eli", "candidate_id": "be-03", "start": "2026-10-14T09:00"})],
             [("finish", {})]]
    llm = PipelineFake(turns)
    out = run_pipeline(llm, JD, load_resumes(PRACTICE / "backend-engineer" / "resumes"), cal(), log=lambda *_: None)
    assert [r.candidate_id for r in out["results"] if r.shortlisted] == ["be-01", "be-02", "be-03"]
    assert set(out["questions"]) == {"be-01", "be-02", "be-03"} and not out["schedule"].unscheduled
    names = {p.name for p in write_outputs(out, tmp_path)}
    assert {"shortlist.md", "questions.md", "schedule.md", "schedule.json"} <= names
    assert "Priya" not in (tmp_path / "shortlist.md").read_text()
    assert "book_slot" in (tmp_path / "schedule.md").read_text()


def test_prf():
    assert prf({"a", "b"}, {"a", "c"}) == (0.5, 0.5, 0.5)
    assert prf(set(), set()) == (1.0, 1.0, 1.0)
    assert prf(set(), {"a"})[2] == 0.0
