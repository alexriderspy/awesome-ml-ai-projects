import json
import re


def resume_from(prompt: str) -> str:
    m = re.search(r"<resume>\n(.*?)</resume>", prompt, re.S)
    return m.group(1) if m else ""


class FakeLLM:

    def __init__(self, bad_first: int = 0, scores: dict | None = None):
        self.prompts: list[tuple[str, str]] = []
        self.bad_first = bad_first
        self.scores = scores or {}

    def complete(self, system: str, user: str) -> str:
        self.prompts.append((system, user))
        resume = resume_from(user)
        bullets = [ln[2:].strip() for ln in resume.splitlines() if ln.startswith("- ")] or [resume.strip()[:40]]
        if "Write 4 to 6 questions" in system:
            return json.dumps({"questions": [
                {"type": "claim", "requirement": "M1", "anchor": bullets[0], "question": "Tell me more about this."},
                {"type": "gap", "requirement": "N1", "anchor": "invented text", "question": "Any payments work?"},
            ]})
        ids = re.findall(r"^([MN]\d+) \(", user, re.M)
        score = next((s for k, s in self.scores.items() if k in resume), 2)
        quote = bullets[0]
        if self.bad_first:
            self.bad_first -= 1
            quote = "an achievement that is nowhere in the resume"
        return json.dumps({"requirements": [{"id": i, "score": score, "evidence": quote if score else ""} for i in ids],
                           "summary": "fake"})


class ScriptedChat:

    def __init__(self, turns: list[list[tuple[str, dict]]]):
        self.turns = list(turns)
        self.seen: list[list[dict]] = []

    def chat(self, messages, tools=None):
        self.seen.append(list(messages))
        if not self.turns:
            return {"content": "done", "tool_calls": []}
        calls = self.turns.pop(0)
        return {"content": "", "tool_calls": [{"id": f"call{n}", "name": name, "arguments": args}
                                              for n, (name, args) in enumerate(calls)]}


class PipelineFake(FakeLLM, ScriptedChat):
    def __init__(self, turns, **kw):
        FakeLLM.__init__(self, **kw)
        ScriptedChat.__init__(self, turns)
