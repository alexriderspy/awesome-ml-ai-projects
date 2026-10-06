import re

from . import checks
from .search import FetchFn, SearchFn, ddgs_search
from .swarm import Agent, Result, RunResult, run

MAX_REVISIONS = 1


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def sources_block(state: dict, ids: list[int]) -> str:
    lines = [f"[{i}] {state['sources'][i]['title']} — {state['sources'][i]['url']}" for i in ids]
    return "## Sources\n\n" + "\n".join(lines) + "\n"


def build_team(search: SearchFn = ddgs_search, fetch: FetchFn | None = None, max_results: int = 5) -> dict[str, Agent]:
    team: dict[str, Agent] = {}

    def transfer_to_researcher() -> Agent:
        """Hand the topic to the Researcher."""
        return team["Researcher"]

    def transfer_to_planner(state: dict) -> Result | Agent:
        """Hand the collected sources to the Planner. Call after you have searched."""
        if not state["sources"]:
            return Result("Error: no sources yet. Call web_search first.")
        return team["Planner"]

    def transfer_to_writer(state: dict) -> Result | Agent:
        """Hand the outline to the Writer. Call after save_outline."""
        if not state.get("outline"):
            return Result("Error: no outline yet. Call save_outline first.")
        return team["Writer"]

    def transfer_to_editor(state: dict) -> Result | Agent:
        """Hand the saved draft to the Editor. Call after save_draft."""
        if not state.get("draft"):
            return Result("Error: no draft yet. Call save_draft first.")
        return team["Editor"]

    def web_search(query: str, state: dict) -> str:
        """Search the web. Returns numbered results; use those numbers as citation ids."""
        hits = search(query, max_results)
        if not hits:
            return "No results. Try a different query."
        lines = []
        for h in hits:
            sid = next((i for i, s in state["sources"].items() if s["url"] == h["url"]), None)
            if sid is None:
                sid = len(state["sources"]) + 1
                state["sources"][sid] = {"title": h["title"], "url": h["url"], "snippet": h["snippet"]}
            lines.append(f"[{sid}] {h['title']} ({h['url']})\n    {h['snippet']}")
        return "\n".join(lines)

    def fetch_page(source_id: int, state: dict) -> str:
        """Read more of a search result's page. Use a source number from web_search."""
        src = state["sources"].get(int(source_id))
        if not src:
            return f"Error: no source [{source_id}]."
        text = fetch(src["url"])
        src["page"] = text
        return f"[{source_id}] {text}"

    def save_outline(title: str, sections: list[str], state: dict) -> str:
        """Save the post plan: a title and 3-5 section lines like 'Heading: what it covers (sources 1, 3)'. Do not include Introduction, Conclusion or Sources; they are added by the Writer."""
        state["outline"] = {"title": title, "sections": list(sections)}
        return "Outline saved:\n# " + title + "\n" + "\n".join(f"- {s}" for s in sections)

    def save_draft(markdown: str, state: dict) -> str:
        """Save the full post in markdown (title, intro, ## sections, ## Conclusion) with inline citations like [2]. Do not write a Sources section; it is built from your citations."""
        body, _ = checks.split_sources(markdown)
        body = body.rstrip()
        ids = sorted(set(checks.cited_ids(body)))
        bad = [i for i in ids if i not in state["sources"]]
        if bad:
            return f"Error: citations {bad} are not search results. Valid ids: {sorted(state['sources'])}. Fix and save again."
        if not ids:
            return "Error: cite at least one source inline like [1]. Fix and save again."
        state["draft"] = body + "\n\n" + sources_block(state, ids)
        return f"Draft saved ({checks.word_count(state['draft'])} words, cites {ids})."

    def check_draft(state: dict) -> str:
        """Run the automatic checks on the saved draft: word budget, structure and citations."""
        urls = {s["url"] for s in state["sources"].values()}
        return checks.editor_report(state["draft"], state["word_budget"], urls)

    def request_revision(feedback: str, state: dict) -> Result:
        """Send the draft back to the Writer with specific feedback. Allowed once."""
        if state["revisions"] >= MAX_REVISIONS:
            return Result("Revision limit reached. Call approve_draft now.")
        state["revisions"] += 1
        state.setdefault("feedback", []).append(feedback)
        return Result(f"Editor feedback for the Writer: {feedback}", agent=team["Writer"])

    def approve_draft(state: dict) -> Result:
        """Approve the draft and hand it back to the Admin."""
        state["approved"] = True
        return Result("Draft approved by the Editor.", agent=team["Admin"])

    def publish(state: dict) -> Result:
        """Publish the approved post. Ends the job."""
        if not state.get("draft"):
            return Result("Error: nothing to publish yet. Hand off to the Researcher.")
        state["final"] = state["draft"]
        return Result("Published.", done=True)

    team["Admin"] = Agent(
        "Admin",
        "You manage a small blog team: Researcher, Planner, Writer, Editor. "
        "When you get a topic, call transfer_to_researcher. "
        "When the Editor hands back an approved draft, call publish. Do not write the post yourself.",
        [transfer_to_researcher, publish],
    )
    researcher_tools = [web_search] + ([fetch_page] if fetch else []) + [transfer_to_planner]
    team["Researcher"] = Agent(
        "Researcher",
        lambda s: (
            f"Research the topic: {s['topic']!r}. Call web_search 2-4 times with different focused queries "
            "(basics, how it works, numbers/facts, history or trade-offs). "
            + ("Use fetch_page on 1-2 of the most useful results for detail. " if fetch else "")
            + "Then call transfer_to_planner. Never invent sources."
        ),
        researcher_tools,
    )
    team["Planner"] = Agent(
        "Planner",
        lambda s: (
            f"Plan a blog post on {s['topic']!r} of about {s['word_budget']} words using only the search results "
            "in the conversation. Call save_outline with a title and 3-4 body sections, noting which source numbers "
            "support each. Then call transfer_to_writer."
        ),
        [save_outline, transfer_to_writer],
    )
    team["Writer"] = Agent(
        "Writer",
        lambda s: (
            f"Write the post from the outline. Target {s['word_budget']} words (stay within "
            f"{int(0.8 * s['word_budget'])}-{int(1.1 * s['word_budget'])}, not counting sources). Format:\n"
            "# Title\n\nAn intro paragraph.\n\n## Section heading (one per outline section)\n...\n\n## Conclusion\n...\n\n"
            "Back each factual claim with an inline citation using the source numbers from web_search, like [2]. "
            "Only cite numbers that appear in the search results. Only state facts found in the results. "
            "Do not write a Sources section. Call save_draft with the whole post, then transfer_to_editor. "
            "If the Editor sent feedback, fix exactly those points and save again."
        ),
        [save_draft, transfer_to_editor],
    )
    team["Editor"] = Agent(
        "Editor",
        lambda s: (
            "Review the saved draft. First call check_draft. If it lists PROBLEMS and "
            f"{'no revision has been requested yet' if s['revisions'] < MAX_REVISIONS else 'the revision limit is used up'}, "
            + ("call request_revision with short, concrete feedback. " if s["revisions"] < MAX_REVISIONS else "")
            + "Otherwise call approve_draft."
        ),
        [check_draft, request_revision, approve_draft],
    )
    return team


def new_state(topic: str, word_budget: int) -> dict:
    return {"topic": topic, "word_budget": word_budget, "sources": {}, "outline": None, "draft": "", "revisions": 0}


def write_post(topic: str, llm, word_budget: int = 600, search: SearchFn = ddgs_search, fetch: FetchFn | None = None,
               max_steps: int = 30, on_event=None) -> RunResult:
    team = build_team(search, fetch)
    state = new_state(topic, word_budget)
    messages = [{"role": "user", "content": f"Write a blog post about: {topic}\nWord budget: about {word_budget} words."}]
    return run(llm, team["Admin"], messages, state, max_steps=max_steps, on_event=on_event)
