# CLI run (deepseek-flash)

Real run on the support-lead practice case. Output files are in [`demo/support-lead/`](support-lead/).

```bash
PYTHONPATH=src python -m recruit_team --jd eval/practice/support-lead/jd.md --resumes eval/practice/support-lead/resumes --out demo/support-lead
```

```text
Screening 6 resumes for: Customer Support Team Lead (B2B SaaS)
  sl-04        fit= 84.8 qualifies=yes quotes 7/7 valid, attempts=1  <- shortlisted
  sl-01        fit= 81.8 qualifies=yes quotes 6/6 valid, attempts=1  <- shortlisted
  sl-06        fit= 60.6 qualifies=yes quotes 6/6 valid, attempts=1  <- shortlisted
  sl-02        fit= 48.5 qualifies=no  quotes 7/7 valid, attempts=1
  sl-03        fit=  9.1 qualifies=no  quotes 2/2 valid, attempts=1
  sl-05        fit=  3.0 qualifies=no  quotes 1/1 valid, attempts=1
Writing interview questions for 3 shortlisted candidates
Scheduling interviews
  step 1: list_interviewers({"panel": "support"}) -> [{"id": "iv-dee", "name": "Dee Fischer", "panels": ["support"]}, {"id": "iv-eli", "name": "Eli Haddad", "panels": ["support", "backend"]}]
  step 2: list_free_slots({"interviewer_id": "iv-dee"}) -> ["2026-10-13T16:15", "2026-10-13T16:30", "2026-10-13T16:45", "2026-10-13T17:00", "2026-10-13T17:15"]
  step 2: list_free_slots({"interviewer_id": "iv-eli"}) -> ["2026-10-14T09:00", "2026-10-14T09:15"]
  step 3: book_slot({"interviewer_id": "iv-eli", "candidate_id": "sl-04", "start": "2026-10-14T09:00"}) -> {"ok": true, "booking": {"interviewer": "iv-eli", "candidate": "sl-04", "start": "2026-10-14T09:00", "end": "2026-10-14T09:45"}}
  step 3: book_slot({"interviewer_id": "iv-dee", "candidate_id": "sl-01", "start": "2026-10-13T16:15"}) -> {"ok": true, "booking": {"interviewer": "iv-dee", "candidate": "sl-01", "start": "2026-10-13T16:15", "end": "2026-10-13T17:00"}}
  step 4: book_slot({"candidate_id": "sl-06", "interviewer_id": "iv-dee", "start": "2026-10-13T17:00"}) -> {"ok": true, "booking": {"interviewer": "iv-dee", "candidate": "sl-06", "start": "2026-10-13T17:00", "end": "2026-10-13T17:45"}}
  step 5: finish({"notes": "Scheduled all 3 Customer Support Team Lead (B2B SaaS) candidates on the support panel:\n- sl-04 with iv-eli (Eli Haddad) on 2026-10-14 09:00\u201309:45\n- sl-01 with iv-dee (Dee Fischer) on 2026-10-13 16:15\u201317:00\n- sl-06 with iv-dee (Dee Fischer) on 2026-10-13 17:00\u201317:45\n\nInterviews spread across both panel interviewers; no overlaps (Dee's two slots are back-to-back)."}) -> {"ok": true}
wrote demo/support-lead/shortlist.md
wrote demo/support-lead/shortlist.json
wrote demo/support-lead/questions.md
wrote demo/support-lead/questions.json
wrote demo/support-lead/schedule.md
wrote demo/support-lead/schedule.json
wrote demo/support-lead/calendar-after.json
LLM calls: 14, tokens in/out: 12221/22808, est. cost $0.0310
```
