import json
from dataclasses import dataclass, field

from .clean import clean_html
from .fetch import Fetcher, HttpFetcher
from .schema import generate_schema, normalize_schema, validate_record

MAX_PAGE_CHARS = 14000

SYSTEM = """You are a web scraping agent. You extract structured records from web pages.

Work like this:
1. fetch_page the start URL.
2. Read the page and call save_records with EVERY matching record on that page. Copy values exactly
   from the page, converted to the field types in the schema (numbers without currency symbols,
   dates as YYYY-MM-DD, booleans as true/false). Use null when a value is not on the page.
   Do not invent records. Skip ads, sidebars and "recommended" boxes unless the user asked for them.
3. If the page links to the next page of the SAME listing (a "next", "older", "page 2" style link),
   fetch it and repeat step 2. Never fetch a page twice. Stop at the last page or the page cap.
4. Call finish with a one-line summary.

Always respond with tool calls. Save records before fetching the next page."""

TOOLS = [
    {"type": "function", "function": {
        "name": "fetch_page",
        "description": "Download a web page and return it as compact markdown, plus links that look like pagination.",
        "parameters": {"type": "object", "properties": {"url": {"type": "string", "description": "Absolute URL"}},
                       "required": ["url"]}}},
    {"type": "function", "function": {
        "name": "save_records",
        "description": "Save extracted records. Each record must match the schema; invalid ones are rejected with reasons.",
        "parameters": {"type": "object", "properties": {"records": {"type": "array", "items": {"type": "object"}}},
                       "required": ["records"]}}},
    {"type": "function", "function": {
        "name": "finish",
        "description": "End the run when every page is done.",
        "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}}},
]


@dataclass
class RunResult:
    records: list[dict]
    schema: dict
    pages: list[str]
    log: list[dict] = field(default_factory=list)
    steps: int = 0
    stop_reason: str = ""
    summary: str = ""


class ScrapeSession:

    def __init__(self, schema: dict, fetcher: Fetcher, max_pages: int = 5):
        self.schema = schema
        self.fetcher = fetcher
        self.max_pages = max_pages
        self.pages: list[str] = []
        self.records: list[dict] = []
        self._keys: set[str] = set()
        self.finished = False
        self.summary = ""

    def fetch_page(self, url: str) -> str:
        url = (url or "").strip()
        if url in self.pages:
            return f"Already fetched {url}. Do not fetch it again."
        if len(self.pages) >= self.max_pages:
            return f"Page cap ({self.max_pages}) reached. Save what you have and call finish."
        try:
            html = self.fetcher(url)
        except Exception as e:
            return f"ERROR fetching {url}: {type(e).__name__}: {e}"
        self.pages.append(url)
        page = clean_html(html, url)
        md = page.markdown
        if len(md) > MAX_PAGE_CHARS:
            md = md[:MAX_PAGE_CHARS] + "\n...[truncated]"
        nxt = [c for c in page.next_candidates() if c["url"] not in self.pages]
        hints = "\n".join(f"- [{c['text'] or c['rel']}]({c['url']})" for c in nxt) or "(none found)"
        return (f"URL: {url}\nTITLE: {page.title}\nPAGES FETCHED: {len(self.pages)}/{self.max_pages}\n\n"
                f"{md}\n\nLINKS THAT MAY BE THE NEXT PAGE:\n{hints}")

    def save_records(self, records) -> str:
        if isinstance(records, dict):
            records = [records]
        if not isinstance(records, list):
            return "ERROR: records must be a list of objects"
        saved, dupes, rejected = 0, 0, []
        key = self.schema["key"]
        for i, rec in enumerate(records):
            clean, errors = validate_record(rec, self.schema)
            if errors:
                rejected.append(f"#{i}: " + "; ".join(errors))
                continue
            k = str(clean[key]).strip().lower()
            if k in self._keys:
                dupes += 1
                continue
            self._keys.add(k)
            self.records.append(clean)
            saved += 1
        msg = f"Saved {saved}, skipped {dupes} duplicates, rejected {len(rejected)}. Total records: {len(self.records)}."
        if rejected:
            msg += "\nRejected (fix and resend these):\n" + "\n".join(rejected[:10])
        return msg

    def finish(self, summary: str = "") -> str:
        self.finished = True
        self.summary = summary
        return "Done."

    def call(self, name: str, args: dict) -> str:
        if name == "fetch_page":
            return self.fetch_page(args.get("url", ""))
        if name == "save_records":
            return self.save_records(args.get("records", []))
        if name == "finish":
            return self.finish(args.get("summary", ""))
        return f"ERROR: unknown tool {name!r}"


def _summarize_args(name: str, args: dict) -> dict:
    if name == "save_records":
        recs = args.get("records")
        return {"records": f"<{len(recs) if isinstance(recs, list) else '?'} records>"}
    return args


def run_agent(url: str, description: str, llm, schema: dict | str | None = None, fetcher: Fetcher | None = None,
              max_pages: int = 5, max_steps: int = 20, verbose: bool = False) -> RunResult:
    schema = normalize_schema(schema) if schema else generate_schema(description, llm)
    session = ScrapeSession(schema, fetcher or HttpFetcher(), max_pages=max_pages)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": (
            f"Start URL: {url}\nWhat to extract: {description}\nPage cap: {max_pages}\n"
            f"Record schema (JSON Schema for one record):\n{json.dumps(schema, indent=1)}")},
    ]
    log: list[dict] = []
    nudged = False
    stop = "step cap reached"
    step = 0
    for step in range(1, max_steps + 1):
        reply = llm.chat(messages, TOOLS)
        calls = reply["tool_calls"]
        if not calls:
            if nudged:
                stop = "model stopped calling tools"
                break
            nudged = True
            messages.append({"role": "assistant", "content": reply["content"] or "(no reply)"})
            messages.append({"role": "user", "content": "Use the tools. Call finish when every page is done."})
            continue
        messages.append({"role": "assistant", "content": reply["content"] or None, "tool_calls": [
            {"id": c["id"], "type": "function",
             "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])}} for c in calls]})
        for c in calls:
            result = session.call(c["name"], c["arguments"])
            entry = {"step": step, "tool": c["name"], "args": _summarize_args(c["name"], c["arguments"]),
                     "result": result.splitlines()[0][:160] if result else ""}
            log.append(entry)
            if verbose:
                print(f"[{step}] {entry['tool']}({json.dumps(entry['args'])}) -> {entry['result']}")
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": result})
        if session.finished:
            stop = "finished"
            break
    return RunResult(records=session.records, schema=schema, pages=session.pages, log=log,
                     steps=step, stop_reason=stop, summary=session.summary)
