import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))
from recruit_team.documents import Resume, load_resumes, parse_jd
from recruit_team.llm import OpenAICompatible
from recruit_team.pipeline import DEFAULT_CALENDAR, run_pipeline
from recruit_team.redact import redact
from recruit_team.scheduler import Calendar

PRACTICE = ROOT / "eval" / "practice"
CASES = sorted(p.name for p in PRACTICE.iterdir() if (p / "jd.md").exists())

st.set_page_config(page_title="Recruitment Agent Team", layout="wide")
st.title("Recruitment Agent Team")
st.caption("Screener → Interviewer → Scheduler. Resumes are redacted (name, age, gender, family status, photo, "
           "contacts) before any model sees them. The calendar is simulated; no invites are sent.")

with st.sidebar:
    case = st.selectbox("Practice job description", CASES)
    jd_text = st.text_area("Job description (edit or paste your own)", (PRACTICE / case / "jd.md").read_text(),
                           height=260)
    uploads = st.file_uploader("Resumes (.md / .txt). Leave empty to use the practice resumes for this job.",
                               type=["md", "txt"], accept_multiple_files=True)
    max_short = st.slider("Max shortlist", 1, 5, 3)
    run = st.button("Run pipeline", type="primary")

if run:
    jd = parse_jd(jd_text)
    resumes = ([Resume(Path(f.name).stem, f.read().decode("utf-8")) for f in uploads] if uploads
               else load_resumes(PRACTICE / case / "resumes"))
    llm = OpenAICompatible()
    with st.status(f"Running 3 agents on {len(resumes)} resumes…", expanded=False) as status:
        out = run_pipeline(llm, jd, resumes, Calendar.load(DEFAULT_CALENDAR), max_shortlist=max_short,
                           log=lambda m: status.write(m))
        status.update(label="Done", state="complete")

    reqs = {r.id: r.text for r in jd.requirements}
    st.subheader("Shortlist")
    st.dataframe(pd.DataFrame([{
        "candidate": r.candidate_id, "fit": r.fit, "must-haves met": "yes" if r.qualifies else "no",
        "shortlisted": "yes" if r.shortlisted else "", "quotes valid": f"{r.quotes_final[0]}/{r.quotes_final[1]}",
        **{i["id"]: i["score"] for i in r.items}} for r in out["results"]]), hide_index=True, use_container_width=True)

    sched, cal = out["schedule"], out["calendar"]
    st.subheader("Schedule")
    names = {i: v.get("name", i) for i, v in cal.interviewers.items()}
    if sched.bookings:
        st.dataframe(pd.DataFrame([{"candidate": b["candidate"], "interviewer": names[b["interviewer"]],
                                    "start": b["start"].replace("T", " "), "end": b["end"][-5:]}
                                   for b in sorted(sched.bookings, key=lambda b: b["start"])]),
                     hide_index=True, use_container_width=True)
    if sched.unscheduled:
        st.warning(f"Not scheduled: {', '.join(sched.unscheduled)}")
    with st.expander(f"Scheduler tool calls ({len(sched.log)} calls, {sched.steps} steps)"):
        for e in sched.log:
            st.markdown(f"{e['step']}. `{e['tool']}({e['args']})` → {e['result']}")
    shortlisted = [r for r in out["results"] if r.shortlisted]
    st.subheader("Evidence and interview questions")
    for r in out["results"]:
        if not r.shortlisted:
            continue
        with st.expander(f"{r.candidate_id} · fit {r.fit} · evidence and interview questions", expanded=r is shortlisted[0]):
            left, right = st.columns(2)
            with left:
                st.markdown("**Evidence (verbatim from the redacted resume)**")
                for i in r.items:
                    ev = f' "{i["evidence"]}"' if i["evidence"] else " no evidence"
                    st.markdown(f"- **{i['id']}** {i['score']}/3 · {reqs[i['id']]}  \n  {ev}")
            with right:
                st.markdown("**Interview questions**")
                for n, q in enumerate(out["questions"].get(r.candidate_id, []), 1):
                    st.markdown(f"{n}. `{q['type']} {q['requirement']}` {q['question']}")

    with st.expander("What the model saw (redacted resumes)"):
        for x in resumes:
            st.markdown(f"**{x.candidate_id}**")
            st.code(redact(x.text).text, language="markdown")
    cost = llm.cost_usd()
    st.caption(f"LLM calls: {llm.usage['calls']} · tokens in/out {llm.usage['input_tokens']}/{llm.usage['output_tokens']}"
               + (f" · est. ${cost:.4f}" if cost is not None else ""))
