import json
import re


def _words(t: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", t)


def _bullets(t: str) -> list[str]:
    return [l for l in t.splitlines() if re.match(r"^\s*[-*•]\s+\S", l)]


def _numbered(t: str) -> list[str]:
    return [l for l in t.splitlines() if re.match(r"^\s*\d+[.)]\s+\S", l)]


def _json_obj(t: str):
    m = re.search(r"\{.*\}", t, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def run_check(kind: str, arg, text: str) -> bool:
    t = text.strip()
    if kind == "max_words":
        return len(_words(t)) <= arg
    if kind == "min_words":
        return len(_words(t)) >= arg
    if kind == "lowercase":
        return t == t.lower() and any(c.isalpha() for c in t)
    if kind == "uppercase":
        return t == t.upper() and any(c.isalpha() for c in t)
    if kind == "includes":
        return all(w.lower() in t.lower() for w in arg)
    if kind == "excludes":
        return not any(w.lower() in t.lower() for w in arg)
    if kind == "bullets":
        return len(_bullets(t)) == arg
    if kind == "numbered":
        return len(_numbered(t)) == arg
    if kind == "json_keys":
        obj = _json_obj(t)
        return isinstance(obj, dict) and set(arg) <= set(obj)
    if kind == "starts_with":
        return t.lower().startswith(arg.lower())
    if kind == "ends_with":
        return t.rstrip(" .!\n").lower().endswith(arg.lower().rstrip(" .!"))
    if kind == "no_char":
        return arg not in t
    if kind == "max_sentences":
        return len([s for s in re.split(r"[.!?]+(?:\s|$)", t) if s.strip()]) <= arg
    raise ValueError(f"unknown check: {kind}")


def score_case(case: dict, text: str) -> tuple[float, list[tuple[str, bool]]]:
    results = [(c["kind"], run_check(c["kind"], c.get("arg"), text)) for c in case["checks"]]
    return sum(ok for _, ok in results) / len(results), results
