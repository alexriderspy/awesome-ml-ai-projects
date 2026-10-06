# Results: deepseek-flash

Real run of `python eval/run_eval.py --results-md demo/results.md --traces demo/traces.json` (max 20 steps per task, 4 tasks in parallel). Steps = model calls. Tokens = prompt + completion from the API usage field. Every tool call is in [`traces.json`](traces.json).

| task | solved | steps | tokens |
|---|---|---|---|
| bill-split | yes | 5 | 6401 |
| birthday-countdown | yes | 5 | 7605 |
| config-merge | yes | 5 | 6245 |
| env-parser | yes | 5 | 5485 |
| express-shipping | yes | 5 | 5380 |
| leaderboard | yes | 5 | 5337 |
| memoize-kwargs | yes | 5 | 5892 |
| note-tags | yes | 5 | 5090 |
| pagination | yes | 5 | 5578 |
| parcel-weights | yes | 5 | 8295 |
| safe-int | yes | 5 | 5708 |
| semver | yes | 5 | 6348 |
| slugify | yes | 5 | 5393 |
| stats-summary | yes | 5 | 5399 |
| tree-depth | yes | 5 | 5807 |
| **average** | **15/15** | **5.0** | **5998** |

OVERALL 100.0/100 (solve rate)
