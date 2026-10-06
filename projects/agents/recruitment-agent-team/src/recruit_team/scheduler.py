import copy
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

FMT = "%Y-%m-%dT%H:%M"


def _t(s: str) -> datetime:
    return datetime.fromisoformat(str(s).strip())


class Calendar:

    def __init__(self, data: dict):
        self.data = copy.deepcopy(data)
        self.slot = timedelta(minutes=int(self.data.get("slot_minutes", 45)))
        self.step = timedelta(minutes=int(self.data.get("step_minutes", 15)))
        self.interviewers = {i["id"]: i for i in self.data["interviewers"]}
        self.bookings: list[dict] = self.data.setdefault("bookings", [])

    @classmethod
    def load(cls, path: str | Path) -> "Calendar":
        return cls(json.loads(Path(path).read_text()))

    def _busy(self, interviewer_id: str, start: datetime, end: datetime, attendee: str = "") -> dict | None:
        for b in self.bookings:
            if (b["interviewer"] == interviewer_id or (attendee and b.get("candidate") == attendee)) \
                    and _t(b["start"]) < end and start < _t(b["end"]):
                return b
        return None

    def _available(self, interviewer_id: str, start: datetime, end: datetime) -> bool:
        return any(_t(w["start"]) <= start and end <= _t(w["end"])
                   for w in self.interviewers[interviewer_id].get("availability", []))

    def list_interviewers(self, panel: str = "") -> list[dict]:
        return [{"id": i["id"], "name": i.get("name", ""), "panels": i.get("panels", [])}
                for i in self.interviewers.values() if not panel or panel in i.get("panels", [])]

    def free_slots(self, interviewer_id: str, date: str = "", limit: int = 12) -> list[str]:
        if interviewer_id not in self.interviewers:
            raise KeyError(f"unknown interviewer {interviewer_id!r}")
        slots = []
        for w in self.interviewers[interviewer_id].get("availability", []):
            s, end = _t(w["start"]), _t(w["end"])
            while s + self.slot <= end:
                if (not date or s.strftime("%Y-%m-%d") == date) and not self._busy(interviewer_id, s, s + self.slot):
                    slots.append(s.strftime(FMT))
                s += self.step
        return slots[:limit]

    def book(self, interviewer_id: str, candidate_id: str, start: str, panel: str = "",
             allowed: set[str] | None = None) -> dict:
        if interviewer_id not in self.interviewers:
            return {"ok": False, "error": f"unknown interviewer {interviewer_id!r}"}
        if panel and panel not in self.interviewers[interviewer_id].get("panels", []):
            return {"ok": False, "error": f"{interviewer_id} is not on the {panel!r} panel"}
        if allowed is not None and candidate_id not in allowed:
            return {"ok": False, "error": f"{candidate_id!r} is not on the shortlist"}
        if any(b.get("candidate") == candidate_id for b in self.bookings):
            return {"ok": False, "error": f"{candidate_id} already has an interview"}
        try:
            s = _t(start)
        except ValueError:
            return {"ok": False, "error": f"bad start time {start!r}, use YYYY-MM-DDTHH:MM"}
        e = s + self.slot
        if not self._available(interviewer_id, s, e):
            return {"ok": False, "error": f"{interviewer_id} is not available {s.strftime(FMT)}-{e.strftime('%H:%M')}"}
        clash = self._busy(interviewer_id, s, e, candidate_id)
        if clash:
            return {"ok": False, "error": f"double booking: overlaps {clash['start']}-{clash['end'][-5:]}"}
        b = {"interviewer": interviewer_id, "candidate": candidate_id, "start": s.strftime(FMT),
             "end": e.strftime(FMT), "new": True}
        self.bookings.append(b)
        return {"ok": True, "booking": {k: v for k, v in b.items() if k != "new"}}

    def conflicts(self) -> list[tuple[dict, dict]]:
        out = []
        for n, a in enumerate(self.bookings):
            for b in self.bookings[n + 1:]:
                if a["interviewer"] == b["interviewer"] and _t(a["start"]) < _t(b["end"]) and _t(b["start"]) < _t(a["end"]):
                    out.append((a, b))
        return out


TOOLS = [
    {"type": "function", "function": {
        "name": "list_interviewers", "description": "List interviewers, optionally only those on a panel.",
        "parameters": {"type": "object", "properties": {"panel": {"type": "string"}}}}},
    {"type": "function", "function": {
        "name": "list_free_slots",
        "description": "Free interview start times (YYYY-MM-DDTHH:MM) for one interviewer, optionally on one date.",
        "parameters": {"type": "object", "properties": {
            "interviewer_id": {"type": "string"}, "date": {"type": "string", "description": "YYYY-MM-DD"}},
            "required": ["interviewer_id"]}}},
    {"type": "function", "function": {
        "name": "book_slot", "description": "Book one interview. Fails on double bookings or outside availability.",
        "parameters": {"type": "object", "properties": {
            "interviewer_id": {"type": "string"}, "candidate_id": {"type": "string"},
            "start": {"type": "string", "description": "YYYY-MM-DDTHH:MM"}},
            "required": ["interviewer_id", "candidate_id", "start"]}}},
    {"type": "function", "function": {
        "name": "finish", "description": "Call when every candidate is booked or cannot be booked.",
        "parameters": {"type": "object", "properties": {"notes": {"type": "string"}}}}},
]

SYSTEM = """You schedule interviews on a simulated calendar using the tools. Rules:
- Book exactly one interview for each candidate id you are given, with an interviewer on the role's panel.
- Look up free slots before booking. Never book over an existing booking; if book_slot fails, pick another slot.
- Spread interviews across interviewers when you can.
- Call finish when done. Do not send emails or invites; the calendar file is the output."""


@dataclass
class ScheduleRun:
    bookings: list[dict] = field(default_factory=list)
    unscheduled: list[str] = field(default_factory=list)
    log: list[dict] = field(default_factory=list)
    steps: int = 0
    finished: bool = False
    notes: str = ""


def _summary(result) -> str:
    s = json.dumps(result)
    return s if len(s) <= 160 else s[:157] + "..."


def run_scheduler(llm, calendar: Calendar, candidates: list[str], panel: str = "", role: str = "",
                  max_steps: int = 20, on_step=None) -> ScheduleRun:
    run = ScheduleRun()
    allowed = set(candidates)
    if not candidates:
        run.finished, run.notes = True, "no candidates to schedule"
        return run

    def dispatch(name: str, args: dict):
        if name == "list_interviewers":
            return calendar.list_interviewers(args.get("panel", panel))
        if name == "list_free_slots":
            try:
                return calendar.free_slots(str(args.get("interviewer_id", "")), str(args.get("date", "") or ""))
            except KeyError as e:
                return {"error": str(e)}
        if name == "book_slot":
            return calendar.book(str(args.get("interviewer_id", "")), str(args.get("candidate_id", "")),
                                 str(args.get("start", "")), panel=panel, allowed=allowed)
        if name == "finish":
            return {"ok": True}
        return {"error": f"unknown tool {name!r}"}

    task = (f"Role: {role or 'unspecified'}\nPanel: {panel or 'any'}\nCandidates to schedule: {', '.join(candidates)}\n"
            f"Each interview lasts {int(calendar.slot.total_seconds() // 60)} minutes.")
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task}]
    for step in range(1, max_steps + 1):
        run.steps = step
        reply = llm.chat(messages, TOOLS)
        calls = reply.get("tool_calls") or []
        if not calls:
            if all(any(b["candidate"] == c for b in calendar.bookings) for c in candidates):
                run.finished, run.notes = True, reply.get("content", "")
                break
            messages += [{"role": "assistant", "content": reply.get("content") or ""},
                         {"role": "user", "content": "Some candidates are not booked yet. Use the tools."}]
            continue
        messages.append({"role": "assistant", "content": reply.get("content") or "", "tool_calls": [
            {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])}}
            for c in calls]})
        for c in calls:
            result = dispatch(c["name"], c["arguments"] if isinstance(c["arguments"], dict) else {})
            entry = {"step": step, "tool": c["name"], "args": c["arguments"], "result": _summary(result)}
            run.log.append(entry)
            if on_step:
                on_step(entry)
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(result)})
            if c["name"] == "finish":
                run.finished, run.notes = True, str(c["arguments"].get("notes", ""))
        if run.finished:
            break
    run.bookings = [{k: v for k, v in b.items() if k != "new"} for b in calendar.bookings if b.get("new")]
    booked = {b["candidate"] for b in run.bookings}
    run.unscheduled = [c for c in candidates if c not in booked]
    return run


def schedule_markdown(run: ScheduleRun, calendar: Calendar) -> str:
    names = {i: v.get("name", i) for i, v in calendar.interviewers.items()}
    out = ["# Interview schedule (simulated calendar, no invites sent)", "",
           "| Candidate | Interviewer | Start | End |", "|---|---|---|---|"]
    for b in sorted(run.bookings, key=lambda b: b["start"]):
        out.append(f"| {b['candidate']} | {names.get(b['interviewer'], b['interviewer'])} ({b['interviewer']}) "
                   f"| {b['start'].replace('T', ' ')} | {b['end'][-5:]} |")
    if run.unscheduled:
        out += ["", f"Not scheduled: {', '.join(run.unscheduled)}"]
    out += ["", f"Agent steps: {run.steps}, finished: {run.finished}", "", "## Tool calls", ""]
    out += [f"{e['step']}. `{e['tool']}({json.dumps(e['args'])})` -> {e['result']}" for e in run.log]
    return "\n".join(out) + "\n"
