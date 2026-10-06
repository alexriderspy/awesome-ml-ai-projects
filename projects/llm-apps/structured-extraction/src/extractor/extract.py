import json
import re
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError

from .compare import is_num, str_match, tokens, value_match
from .schemas import SCHEMAS

SYSTEM = """You extract structured data from messy text (OCR receipts, emails, chat posts).
Reply with one JSON object only, matching this JSON schema:
{schema}
Rules:
- copy values from the text; use null when a field is not stated and can't be inferred
- dates as YYYY-MM-DD; money as plain numbers (no symbols, no thousands separators)
- read the text's own number format (1,89 means 1.89 in Europe; 8 LPA means 800000)"""


@dataclass
class Extraction:
    data: dict | None
    attempts: int
    errors: list[str] = field(default_factory=list)
    confidence: dict[str, float | None] = field(default_factory=dict)

    @property
    def valid(self) -> bool:
        return self.data is not None


def parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found in the reply")
    return json.loads(text[start : end + 1])


def _chat(llm, messages, temperature):
    try:
        return llm.chat(messages, temperature=temperature)
    except TypeError:
        return llm.chat(messages)


def extract_once(text: str, schema: type[BaseModel], llm, retries: int = 2, temperature: float = 0.0) -> Extraction:
    system = SYSTEM.format(schema=json.dumps(schema.model_json_schema()))
    messages = [{"role": "system", "content": system}, {"role": "user", "content": text}]
    errors = []
    for attempt in range(1, retries + 2):
        reply = _chat(llm, messages, temperature)
        try:
            obj = schema.model_validate(parse_json(reply))
            return Extraction(obj.model_dump(mode="json"), attempt, errors)
        except (ValueError, ValidationError) as e:
            err = _short_error(e)
            errors.append(err)
            messages += [
                {"role": "assistant", "content": reply},
                {"role": "user", "content": f"That JSON failed validation:\n{err}\nFix it and reply with the corrected JSON only."},
            ]
    return Extraction(None, retries + 1, errors)


def _short_error(e: Exception) -> str:
    if isinstance(e, ValidationError):
        return "\n".join(f"- {'.'.join(map(str, x['loc'])) or 'object'}: {x['msg']}" for x in e.errors()[:8])
    return f"- {e}"


def grounded(value, text: str) -> bool | None:
    if value is None or isinstance(value, bool):
        return None
    if is_num(value):
        v = float(value)
        forms = {f"{v:.2f}", f"{v:,.2f}", f"{v:.2f}".replace(".", ","), f"{v:,.0f}" if v == int(v) else f"{v:g}"}
        if v == int(v):
            forms.add(str(int(v)))
        flat = text.replace(" ", "")
        return any(re.search(rf"(?<![\d.,]){re.escape(f)}(?![\d])", flat) for f in forms)
    s = str(value)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) or s in ("onsite", "hybrid", "remote", "full-time", "part-time",
                                                      "contract", "internship", "cash", "card", "mobile", "other"):
        return None
    if re.fullmatch(r"[A-Z]{3}", s):
        return None
    want = tokens(s)
    return bool(want) and want <= tokens(text)


def _agreement(path: str, value, samples: list[dict]) -> float | None:
    if not samples:
        return None
    key, _, sub = path.partition("[")
    hits = 0
    for s in samples:
        if key == "items":
            name = value.get("name", "")
            hits += any(str_match(it.get("name", ""), name) and value_match(it.get("total"), value.get("total"))
                        for it in s.get("items") or [])
        elif key == "skills":
            hits += any(str_match(x, value) for x in s.get("skills") or [])
        else:
            hits += value_match(s.get(key), value)
    return hits / len(samples)


def field_confidence(data: dict, samples: list[dict], text: str) -> dict[str, float | None]:
    out = {}
    for key, value in data.items():
        entries = [(f"{key}[{i}]", v) for i, v in enumerate(value)] if isinstance(value, list) else [(key, value)]
        for path, v in entries:
            g = grounded(v.get("name") if isinstance(v, dict) else v, text)
            a = _agreement(path, v, samples)
            signals = [x for x in (None if g is None else float(g), a) if x is not None]
            out[path] = round(sum(signals) / len(signals), 2) if signals else None
    return out


def extract(text: str, schema_name: str, llm, retries: int = 2, samples: int = 0) -> Extraction:
    schema = SCHEMAS[schema_name]
    main = extract_once(text, schema, llm, retries=retries)
    if main.valid:
        extra = [extract_once(text, schema, llm, retries=0, temperature=0.8) for _ in range(samples)]
        main.confidence = field_confidence(main.data, [e.data for e in extra if e.valid], text)
    return main
