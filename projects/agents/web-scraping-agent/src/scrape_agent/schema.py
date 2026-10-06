import json
import re

from .llm import ChatModel, parse_json

TYPES = {"string", "number", "integer", "boolean"}

SCHEMA_SYSTEM = """You design a JSON Schema for records a web scraper will extract.
Reply with ONLY a JSON object like:
{"type": "object",
 "properties": {"name": {"type": "string", "description": "..."}, "price": {"type": "number", "description": "..."}},
 "required": ["name"],
 "key": "name"}
Rules:
- 2 to 8 properties, snake_case names, types from: string, number, integer, boolean.
- Prices and counts are numbers without currency symbols. Dates are strings in YYYY-MM-DD.
- Say the expected format in each description.
- "key" is the property that uniquely identifies a record.
- Only fields the user asked for, plus a key if they did not name one."""


def generate_schema(description: str, llm: ChatModel) -> dict:
    raw = parse_json(llm.complete(SCHEMA_SYSTEM, f"What to extract: {description}"))
    return normalize_schema(raw)


def normalize_schema(schema: dict | str) -> dict:
    if isinstance(schema, str):
        schema = json.loads(schema)
    if schema.get("type") == "array" and isinstance(schema.get("items"), dict):
        schema = schema["items"]
    props = schema.get("properties") or {}
    if not props:
        raise ValueError("Schema needs at least one property")
    clean = {}
    for name, spec in props.items():
        spec = dict(spec or {})
        t = spec.get("type", "string")
        if isinstance(t, list):
            t = next((x for x in t if x != "null"), "string")
        spec["type"] = t if t in TYPES else "string"
        clean[name] = spec
    required = [r for r in schema.get("required", []) if r in clean]
    key = schema.get("key") if schema.get("key") in clean else (required[0] if required else next(iter(clean)))
    if key not in required:
        required.insert(0, key)
    return {"type": "object", "properties": clean, "required": required, "key": key}


def _coerce(value, t: str):
    if value is None:
        return None, None
    if t == "string":
        return (value, None) if isinstance(value, str) else (str(value), None)
    if t == "boolean":
        if isinstance(value, bool):
            return value, None
        if isinstance(value, str) and value.strip().lower() in ("true", "yes", "false", "no"):
            return value.strip().lower() in ("true", "yes"), None
        return value, f"expected boolean, got {value!r}"
    if t in ("number", "integer"):
        if isinstance(value, bool):
            return value, f"expected {t}, got boolean"
        if isinstance(value, (int, float)):
            return (int(value) if t == "integer" and float(value).is_integer() else value), None
        if isinstance(value, str) and re.fullmatch(r"-?\d+(\.\d+)?", value.strip().replace(",", "")):
            num = float(value.strip().replace(",", ""))
            return (int(num) if t == "integer" and num.is_integer() else num), None
        return value, f"expected {t}, got {value!r}"
    return value, None


def validate_record(record, schema: dict) -> tuple[dict | None, list[str]]:
    if not isinstance(record, dict):
        return None, [f"record must be an object, got {type(record).__name__}"]
    out, errors = {}, []
    for name, spec in schema["properties"].items():
        val, err = _coerce(record.get(name), spec["type"])
        if err:
            errors.append(f"{name}: {err}")
        out[name] = val
    for name in schema["required"]:
        if out.get(name) in (None, ""):
            errors.append(f"{name}: required")
    return (None, errors) if errors else (out, [])
