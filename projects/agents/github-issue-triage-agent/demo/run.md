# Demo run

Real output from `deepseek-flash` (via https://api.deepseek.com) on three untriaged issues: a reworded duplicate (#44), a report with no details (#49), and a bug in the same area as two other issues that is not a duplicate of either (#41). Nothing was posted anywhere; labels, duplicate marks and drafts only live in the agent's workspace.

```bash
PYTHONPATH=src python -m issue_triage triage 44 49 41
```

```text

=== #44 Feed readers show my posts one day early
  [1] get_issue({"number": 44}) -> #44 'Feed readers show my posts one day early'
  [2] search_issues({"query": "feed pubDate date timezone"}) -> 5 hits: #3 (11.34), #17 (4.64), #52 (4.31), #34 (3.78), #38 (3.47)
  [2] search_issues({"query": "RSS feed date one day early"}) -> 5 hits: #3 (14.9), #52 (8.35), #17 (4.64), #34 (3.78), #38 (3.47)
  [2] search_issues({"query": "timezone post date wrong"}) -> 5 hits: #34 (5.83), #3 (5.47), #40 (5.24), #12 (4.12), #13 (3.82)
  [3] get_issue({"number": 3}) -> #3 'RSS feed shows post dates shifted by one day'
  [4] apply_label({"number": 44, "labels": ["bug"]}) -> labels = bug
  [4] mark_duplicate({"number": 44, "of": 3}) -> duplicate of #3
  [5] draft_reply({"number": 44, "body": "Thanks for the detailed report, Bruno — and you've diagnosed it exactly righ) -> draft saved (80 words)
  labels:       bug
  duplicate of: #3
  draft reply:
    | Thanks for the detailed report, Bruno — and you've diagnosed it exactly right. feed.xml
    | emits pubDate as midnight UTC, so anyone west of UTC sees the previous day; that's the
    | same root cause as #3, so I'm closing this as a duplicate and tracking the fix there. A
    | fix would likely use the timezone from tinsel.toml (or default to noon), and your
    | Vancouver example is a useful data point. If you can add your tinsel version to #3, that
    | helps.
  steps=6 (done)  tokens=12426+862  cost=$0.00384  time=7.8s

=== #49 it doesnt work
  [1] get_issue({"number": 49}) -> #49 'it doesnt work'
  [2] search_issues({"query": "tinsel doesn't work nothing happens"}) -> 5 hits: #8 (6.38), #5 (4.12), #45 (3.49), #15 (3.38), #52 (3.3)
  [2] search_issues({"query": "command does nothing after install"}) -> 5 hits: #12 (4.86), #13 (4.66), #33 (3.65), #47 (3.29), #46 (2.74)
  [2] search_issues({"query": "cannot run tinsel build error not working"}) -> 5 hits: #20 (5.04), #47 (4.65), #60 (4.46), #6 (4.31), #59 (4.02)
  [3] get_issue({"number": 12}) -> #12 'Something broke after upgrading'
  [3] search_issues({"query": "getting started how to use tinsel first build nothing happens"}) -> 5 hits: #10 (4.9), #15 (4.49), #47 (4.12), #57 (4.04), #60 (3.73)
  [4] apply_label({"number": 49, "labels": ["bug", "needs-repro"]}) -> labels = bug, needs-repro
  [5] draft_reply({"number": 49, "body": "Thanks for the report, and sorry you're stuck! Right now there's not enough ) -> draft saved (66 words)
  labels:       bug, needs-repro
  duplicate of: -
  draft reply:
    | Thanks for the report, and sorry you're stuck! Right now there's not enough here for us to
    | dig in. Could you share:  - the tinsel version (`tinsel --version`) - your OS - the exact
    | commands you ran, and the full output/error text  A minimal example (or a link to your
    | repo and `tinsel.toml`) would help a lot. Once we can reproduce it we'll take a look.
  steps=6 (done)  tokens=13174+1210  cost=$0.00420  time=9.6s

=== #41 `serve --watch` crashes when a file is deleted
  [1] get_issue({"number": 41}) -> #41 '`serve --watch` crashes when a file is deleted'
  [2] search_issues({"query": "serve --watch crash file deleted"}) -> 5 hits: #18 (6.56), #8 (4.95), #39 (3.95), #37 (3.79), #59 (3.26)
  [2] search_issues({"query": "watch FileNotFoundError"}) -> 3 hits: #18 (4.0), #37 (2.31), #8 (2.1)
  [2] search_issues({"query": "serve watch rename file"}) -> 5 hits: #18 (6.56), #8 (4.95), #39 (3.95), #37 (3.79), #59 (3.26)
  [3] get_issue({"number": 18}) -> #18 'Memory usage climbs during long `serve --watch` sessions'
  [3] get_issue({"number": 8}) -> #8 "Live reload doesn't pick up CSS changes"
  [3] get_issue({"number": 37}) -> #37 'Stylesheet edits need a server restart to show up'
  [4] apply_label({"number": 41, "labels": ["bug"]}) -> labels = bug
  [4] draft_reply({"number": 41, "body": "Thanks for the report, Paulo — that's a clear one to reproduce, and the trac) -> draft saved (79 words)
  labels:       bug
  duplicate of: -
  draft reply:
    | Thanks for the report, Paulo — that's a clear one to reproduce, and the traceback points
    | right at the watcher re-reading a path that no longer exists.  Deleting or renaming a file
    | should just trigger a rebuild (and drop the stale output), not take the server down. We'll
    | make the watch handler tolerate paths that vanish between the event and the rebuild.
    | Version (1.0.1) and OS (Ubuntu 24.04) noted, so no further info needed. Watch this issue
    | for updates.
  steps=5 (done)  tokens=9966+754  cost=$0.00311  time=6.3s

3 issues  avg tokens/issue=12797  total cost=$0.0111
```

The search tool on its own (pure-Python BM25, no LLM). Here the query is #44's own title, so #44 ranks first (inside the agent, the issue being triaged is excluded from results) and the original #3 comes second:

```bash
PYTHONPATH=src python -m issue_triage search "feed readers show my posts one day early"
```

```text
#44  25.80  [open] Feed readers show my posts one day early  []
#3   12.61  [open] RSS feed shows post dates shifted by one day  ['bug']
#17   9.25  [open] Draft posts show up in feed.xml  ['bug']
#52   6.11  [open] Unpublished posts leak into the RSS feed  []
#56   3.91  [open] Chinese post titles produce the URL /posts//  []
```
