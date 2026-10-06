import inspect
import re
import types
import typing
from dataclasses import dataclass
from typing import Any, Callable, Literal

PRIMITIVES = {str: "string", int: "integer", float: "number", bool: "boolean"}


def type_to_schema(tp: Any) -> dict:
    origin = typing.get_origin(tp)
    args = typing.get_args(tp)
    if tp in PRIMITIVES:
        return {"type": PRIMITIVES[tp]}
    if origin is Literal:
        values = list(args)
        schema = type_to_schema(type(values[0]))
        schema["enum"] = values
        return schema
    if origin in (list, tuple, set) or tp in (list, tuple, set):
        schema: dict = {"type": "array"}
        if args:
            schema["items"] = type_to_schema(args[0])
        return schema
    if origin is dict or tp is dict:
        return {"type": "object"}
    if origin in (typing.Union, types.UnionType):
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return type_to_schema(non_none[0])
        return {"anyOf": [type_to_schema(a) for a in non_none]}
    raise TypeError(f"Unsupported type hint for a tool parameter: {tp!r}")


def parse_docstring(doc: str | None) -> tuple[str, dict[str, str]]:
    lines = inspect.cleandoc(doc or "").splitlines()
    summary, params, section, current = [], {}, "summary", None
    for line in lines:
        stripped = line.strip()
        header = stripped.lower().rstrip(":")
        if stripped.endswith(":") and header in ("args", "arguments", "parameters", "returns", "raises", "example", "examples"):
            section = "args" if header in ("args", "arguments", "parameters") else "other"
            continue
        if section == "summary":
            summary.append(stripped)
        elif section == "args" and stripped:
            m = re.match(r"^(\w+)\s*(?:\([^)]*\))?\s*:\s*(.*)$", stripped)
            if m:
                current = m.group(1)
                params[current] = m.group(2)
            elif current:
                params[current] += " " + stripped
    description = re.sub(r"\s+", " ", " ".join(summary)).strip()
    return description, params


def function_to_schema(fn: Callable, name: str | None = None) -> dict:
    description, param_docs = parse_docstring(fn.__doc__)
    hints = typing.get_type_hints(fn)
    properties, required = {}, []
    for pname, param in inspect.signature(fn).parameters.items():
        if pname not in hints:
            raise TypeError(f"{fn.__name__}: parameter '{pname}' needs a type hint")
        prop = type_to_schema(hints[pname])
        if pname in param_docs:
            prop["description"] = param_docs[pname]
        if param.default is inspect.Parameter.empty:
            required.append(pname)
        elif param.default is not None:
            prop["default"] = param.default
        properties[pname] = prop
    return {
        "type": "function",
        "function": {
            "name": name or fn.__name__,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


@dataclass
class Tool:

    fn: Callable
    schema: dict

    @property
    def name(self) -> str:
        return self.schema["function"]["name"]

    def __call__(self, *args, **kwargs):
        return self.fn(*args, **kwargs)


def tool(fn: Callable | None = None, *, name: str | None = None):
    if fn is None:
        return lambda f: Tool(f, function_to_schema(f, name))
    return Tool(fn, function_to_schema(fn, name))


def check_args(args: dict, parameters: dict) -> str | None:
    props = parameters.get("properties", {})
    missing = [p for p in parameters.get("required", []) if p not in args]
    if missing:
        return f"missing required argument(s): {', '.join(missing)}"
    unknown = [a for a in args if a not in props]
    if unknown:
        return f"unknown argument(s): {', '.join(unknown)}; expected {', '.join(props)}"
    for key, value in args.items():
        problem = _check_value(value, props[key])
        if problem:
            return f"argument '{key}' {problem}"
    return None


def _check_value(value: Any, schema: dict) -> str | None:
    if "anyOf" in schema:
        if all(_check_value(value, s) for s in schema["anyOf"]):
            return f"has the wrong type ({type(value).__name__})"
        return None
    t = schema.get("type")
    ok = {
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "array": isinstance(value, list),
        "object": isinstance(value, dict),
    }.get(t, True)
    if not ok:
        return f"should be {t}, got {type(value).__name__} {value!r}"
    if "enum" in schema and value not in schema["enum"]:
        return f"must be one of {schema['enum']}, got {value!r}"
    if t == "array" and "items" in schema:
        for item in value:
            problem = _check_value(item, schema["items"])
            if problem:
                return f"item {problem}"
    return None
