# Demo run - 2026-10-06

A real run against the live Hacker News API with `deepseek-flash`, at 08:31 UTC on 2026-10-06.
Profile: [`profiles/example.yaml`](../profiles/example.yaml). Output: [`brief-2026-10-06.md`](brief-2026-10-06.md).

```console
$ export LLM_BASE_URL=https://api.deepseek.com LLM_MODEL=deepseek-flash LLM_API_KEY=...
$ PYTHONPATH=src python -m hn_brief --profile profiles/example.yaml --rerank --comments --pages
[hn_brief] fetched 60 stories (HN API)
[hn_brief] stage 1 (BM25 keywords): 49970871=4.96, 49970667=3.33, 49969183=2.98, 49971846=2.85, 49971719=2.30
[hn_brief] stage 2 (LLM rerank): 49970871=9.0, 49969183=9.0, 49971523=8.0, 49961057=8.0, 49970667=7.0
[hn_brief] enriched shortlist: comments for 5/5, page text for 4/5
[hn_brief] summarized 5 stories
[hn_brief] wrote briefs/2026-10-06.md

real	0m16.508s
```

(The brief was written to a scratch folder and copied here; the path in the last log line is shortened.)

What the two stages did:

- Stage 1 (BM25 keyword match) put the ChatGPT cartoon-signature story (49971846) and the Deno/Node post (49971719) in its top 5.
- Stage 2 (LLM rerank of the top 15) swapped those for the Flock public-records story (49971523) and a story about Anthropic reporting a Claude diary entry to police (49961057). The second one matched no keyword at all. It was in the top 15 only because of the popularity prior (716 points, 556 comments), and the LLM read it as relevant to someone building LLM features who cares about privacy.
- 4 of 5 linked pages gave usable text. One fetch failed or returned non-HTML and was skipped, so that summary used the title and top comments only.
- Nothing was posted to Slack (no `--send-slack`).
