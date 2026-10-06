# Demo run: live ddgs search + deepseek-flash

Command (run 2026-10-06, `LLM_MODEL=deepseek-flash`, `LLM_BASE_URL=https://api.deepseek.com`):

```bash
PYTHONPATH=src python -m blog_writer "How the James Webb Space Telescope keeps its instruments cold" \
    --words 600 --fetch --out demo/post-james-webb-space-telescope-cooling.md
```

Handoff trace (stderr). Each line is `[step] active-agent tool(args) -> result summary`; `==>` lines are handoffs.

```text
[01] Admin      transfer_to_researcher() -> Handing off to Researcher.
[01] Admin      ==> handoff to Researcher
[02] Researcher web_search(query='How does the James Webb Space Telescope keep its instruments cold') -> [1] James Webb Space Telescope sunshield - Wikipedia (https://en.wikipedia.org/wiki/James_Webb_Space_Telescope_sunshield) The James Webb Space Telescope (JWST)…
[02] Researcher web_search(query='JWST sunshield five layers how it works temperature Kelvin') -> [1] James Webb Space Telescope sunshield - Wikipedia (https://en.wikipedia.org/wiki/James_Webb_Space_Telescope_sunshield) By keeping the telescope and instrume…
[03] Researcher web_search(query='JWST MIRI cryocooler helium how it works 7 kelvin') -> [10] Cryocooler - NASA Science (https://science.nasa.gov/mission/webb/cryocooler/) Aug 12, 2024 · Cryocooler Webb's MIRI instrument carries detectors that need…
[03] Researcher web_search(query='JWST L2 orbit sunshield Kapton material thickness size facts') -> [1] James Webb Space Telescope sunshield - Wikipedia (https://en.wikipedia.org/wiki/James_Webb_Space_Telescope_sunshield) The JWST sunshield is about 21 m × 14…
[04] Researcher fetch_page(source_id='2') -> [2] How Does Webb Stay Cold? - NASA Science Search Suggested Searches ISS Roman Webb Quesst Moon Base View All Topics A-Z Home Missions Humans in Space Earth T…
[04] Researcher fetch_page(source_id='6') -> [6] Webb's Sunshield - NASA Science Search Suggested Searches ISS Roman Webb Quesst Moon Base View All Topics A-Z Home Missions Humans in Space Earth The Solar…
[05] Researcher web_search(query='JWST sunshield hot side 383 kelvin cold side 40 kelvin L2 point why not Hubble') -> [1] James Webb Space Telescope sunshield - Wikipedia (https://en.wikipedia.org/wiki/James_Webb_Space_Telescope_sunshield) In this artist's view (not to scale),…
[06] Researcher transfer_to_planner() -> Handing off to Planner.
[06] Researcher ==> handoff to Planner
[07] Planner    save_outline(title='Shade in Space: How the James Webb Space Telescope Keeps Its Instruments Cold', sections='["Why Webb Has to Be Cold: infrared light is essentially heat energy, so the te…') -> Outline saved: # Shade in Space: How the James Webb Space Telescope Keeps Its Instruments Cold - Why Webb Has to Be Cold: infrared light is essentially heat en…
[08] Planner    transfer_to_writer() -> Handing off to Writer.
[08] Planner    ==> handoff to Writer
[09] Writer     save_draft(markdown='# Shade in Space: How the James Webb Space Telescope Keeps Its Instruments Cold…') -> Draft saved (703 words, cites [1, 2, 3, 4, 6, 10, 13, 14, 17, 18]).
[10] Writer     save_draft(markdown='# Shade in Space: How the James Webb Space Telescope Keeps Its Instruments Cold…') -> Draft saved (611 words, cites [1, 2, 3, 4, 6, 10, 13, 14, 17, 18]).
[11] Writer     transfer_to_editor() -> Handing off to Editor.
[11] Writer     ==> handoff to Editor
[12] Editor     check_draft() -> words=611 (budget 600); structure={'title': True, 'intro': True, 'sections': True, 'conclusion': True, 'sources': True}; cited=[1, 2, 3, 4, 6, 10, 13, 14, 17, …
[13] Editor     approve_draft() -> Draft approved by the Editor.
[13] Editor     ==> handoff to Admin
[14] Admin      publish() -> Published.

stopped: done after 14 steps, 18 sources, 0 revision(s)

```

The final post (stdout) is saved as [`post-james-webb-space-telescope-cooling.md`](post-james-webb-space-telescope-cooling.md).
