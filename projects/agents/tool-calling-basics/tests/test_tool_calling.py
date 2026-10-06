import json
import sys
from pathlib import Path
from typing import Literal

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from run_eval import answer_score, load_tasks, numbers_in, stub_weather, tool_score
from tool_calling.agent import TraceEntry, run_agent
from tool_calling.calculator import CalcError, evaluate, format_number
from tool_calling.notes import NotesStore
from tool_calling.schema import check_args, function_to_schema, tool
from tool_calling.toolbox import default_tools
from tool_calling.units import UnitError, convert
from tool_calling.weather import current_weather


def test_function_to_schema_types_defaults_and_docs():
    def book(city: str, nights: int, budget: float = 100.0, pets: bool = False,
             tags: list[str] | None = None, room: Literal["single", "double"] = "single") -> str:
        """Book a hotel room.

        Args:
            city: Where to stay.
            nights: How many nights.
            room: Room size.
        """

    s = function_to_schema(book)["function"]
    assert s["name"] == "book" and s["description"] == "Book a hotel room."
    p = s["parameters"]
    assert p["required"] == ["city", "nights"]
    props = p["properties"]
    assert props["city"] == {"type": "string", "description": "Where to stay."}
    assert props["nights"]["type"] == "integer"
    assert props["budget"] == {"type": "number", "default": 100.0}
    assert props["pets"]["type"] == "boolean"
    assert props["tags"] == {"type": "array", "items": {"type": "string"}}
    assert props["room"]["enum"] == ["single", "double"]


def test_missing_type_hint_is_an_error():
    def f(x):
        """No hints."""

    with pytest.raises(TypeError):
        function_to_schema(f)


def test_tool_decorator_keeps_function_callable():
    @tool
    def add(a: int, b: int = 1) -> int:
        """Add."""
        return a + b

    assert add.name == "add" and add(2) == 3


def test_check_args():
    params = {"type": "object", "properties": {"n": {"type": "integer"}, "x": {"type": "number"}},
              "required": ["n"]}
    assert check_args({"n": 3, "x": 2}, params) is None
    assert "missing" in check_args({}, params)
    assert "should be integer" in check_args({"n": "3"}, params)
    assert "should be integer" in check_args({"n": True}, params)
    assert "unknown" in check_args({"n": 1, "y": 2}, params)


@pytest.mark.parametrize("expr,expected", [
    ("2 + 3 * 4", 14), ("(2 + 3) * 4", 20), ("2 ** 10", 1024), ("2^10", 1024), ("-3 + 5", 2),
    ("sqrt(16) + abs(-2)", 6), ("max(1, 4) * 2", 8), ("7 // 2", 3), ("7 % 4", 3),
])
def test_calculator(expr, expected):
    assert evaluate(expr) == expected


@pytest.mark.parametrize("expr", ["__import__('os')", "open('x')", "(1).real", "a + 1", "9 ** 9 ** 9", "1/0", "lambda: 1"])
def test_calculator_rejects_unsafe_or_bad(expr):
    with pytest.raises(CalcError):
        evaluate(expr)


def test_format_number():
    assert format_number(12.0) == "12" and format_number(0.1 + 0.2) == "0.3" and format_number(7) == "7"


@pytest.mark.parametrize("v,a,b,expected", [
    (1, "mi", "km", 1.609344), (1, "ft", "in", 12), (100, "c", "f", 212), (32, "fahrenheit", "celsius", 0),
    (0, "c", "k", 273.15), (1, "lb", "oz", 16), (1, "gal", "l", 3.785411784), (1, "cup", "tbsp", 16),
    (1, "st", "lb", 14), (2, "Litres", "ml", 2000),
])
def test_units(v, a, b, expected):
    assert convert(v, a, b) == pytest.approx(expected)


def test_units_errors():
    with pytest.raises(UnitError, match="cannot convert volume"):
        convert(2, "l", "g")
    with pytest.raises(UnitError, match="unknown unit"):
        convert(1, "parsec", "m")


def test_notes_store(tmp_path):
    store = NotesStore(tmp_path / "n.json")
    assert store.all() == []
    store.add("Buy rice", ["Shopping"])
    store.add("Call the plumber about the sink")
    assert [n["id"] for n in store.all()] == [1, 2]
    assert store.all()[0]["tags"] == ["shopping"]
    assert store.search("plumber sink")[0]["id"] == 2
    assert store.search("shopping")[0]["id"] == 1
    assert store.search("zebra") == []


def test_weather_uses_geocoding_then_forecast():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.url.host)
        if "geocoding" in req.url.host:
            assert req.url.params["name"] == "Pune"
            return httpx.Response(200, json={"results": [{"name": "Pune", "country": "India", "latitude": 18.5, "longitude": 73.9}]})
        assert req.url.params["latitude"] == "18.5"
        return httpx.Response(200, json={"current": {"time": "2026-01-01T10:00", "temperature_2m": 24.3,
                                                     "relative_humidity_2m": 40, "wind_speed_10m": 5.0, "weather_code": 2}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        w = current_weather("Pune", client)
    assert seen == ["geocoding-api.open-meteo.com", "api.open-meteo.com"]
    assert w["temperature_c"] == 24.3 and w["conditions"] == "partly cloudy" and w["country"] == "India"


def test_weather_unknown_city():
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={}))
    with httpx.Client(transport=transport) as client, pytest.raises(RuntimeError, match="no place"):
        current_weather("Nowhereville", client)


class ScriptedLLM:
    """Replays a list of replies and records every message list it was sent."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    def chat(self, messages, tools=None):
        self.seen.append(json.loads(json.dumps(messages)))
        return self.replies.pop(0)


def call(cid, name, args, raw=None):
    return {"id": cid, "name": name, "arguments": args, "raw_arguments": raw or json.dumps(args)}


def reply(content="", calls=()):
    return {"content": content, "tool_calls": list(calls)}


@pytest.fixture
def tools(tmp_path):
    return default_tools(tmp_path / "notes.json", weather_fetch=stub_weather)


def test_parallel_calls_each_get_matching_tool_message(tools):
    llm = ScriptedLLM([
        reply(calls=[call("a", "get_weather", {"city": "Oslo"}), call("b", "get_weather", {"city": "Cairo"})]),
        reply("Cairo is warmer by 21.6 C."),
    ])
    res = run_agent("warmer?", llm, tools)
    assert res.answer == "Cairo is warmer by 21.6 C." and res.steps == 2
    assert [e.batch_size for e in res.trace] == [2, 2]
    second = llm.seen[1]
    assert [tc["id"] for tc in second[-3]["tool_calls"]] == ["a", "b"]
    tool_msgs = second[-2:]
    assert [m["tool_call_id"] for m in tool_msgs] == ["a", "b"]
    assert json.loads(tool_msgs[1]["content"])["temperature_c"] == 29.1


def test_error_paths_are_returned_to_the_model(tools):
    llm = ScriptedLLM([
        reply(calls=[
            call("1", "teleport", {"to": "Mars"}),
            call("2", "calculator", {"_raw": "{expression: 1+1"}, raw="{expression: 1+1"),
            call("3", "unit_convert", {"value": "ten", "from_unit": "km", "to_unit": "mi"}),
            call("4", "calculator", {"expression": "1/0"}),
            call("5", "get_weather", {"city": "Atlantis"}),
        ]),
        reply("Sorry, those all failed."),
    ])
    res = run_agent("break things", llm, tools)
    errors = [e.result for e in res.trace]
    assert all(not e.ok for e in res.trace)
    assert "unknown tool 'teleport'" in errors[0]
    assert "not valid JSON" in errors[1]
    assert "should be number" in errors[2]
    assert "division by zero" in errors[3]
    assert "no place" in errors[4]
    assert [m["tool_call_id"] for m in llm.seen[1] if m["role"] == "tool"] == ["1", "2", "3", "4", "5"]


def test_step_cap(tools):
    loop = [reply(calls=[call(str(i), "calculator", {"expression": "1+1"})]) for i in range(3)]
    res = run_agent("loop forever", ScriptedLLM(loop), tools, max_steps=3)
    assert res.stopped and res.steps == 3 and len(res.trace) == 3


def test_reasoning_content_is_sent_back(tools):
    first = reply(calls=[call("x", "calculator", {"expression": "2*3"})])
    first["reasoning_content"] = "need maths"
    llm = ScriptedLLM([first, reply("6")])
    run_agent("2*3?", llm, tools)
    assert llm.seen[1][-2]["reasoning_content"] == "need maths"


def test_notes_tools_write_the_file(tools, tmp_path):
    llm = ScriptedLLM([reply(calls=[call("n", "add_note", {"text": "water the plants"})]), reply("Saved.")])
    run_agent("note it", llm, tools)
    assert NotesStore(tmp_path / "notes.json").all()[0]["text"] == "water the plants"


def test_numbers_in_handles_commas_and_markdown():
    assert numbers_in("**6,915,641** and -2.5°C") == [6915641, -2.5]


def test_answer_and_tool_scoring():
    spec = {"numbers": [[21.6, 0.05]], "contains": [["cairo"]]}
    assert answer_score("Cairo, by 21.6 C", spec) == 1.0
    assert answer_score("Oslo, by 20 C", spec) == 0.0
    task = {"tools": ["get_weather", "calculator"], "parallel": "get_weather"}
    par = [TraceEntry(1, "get_weather", {}, "", True, "a", 2), TraceEntry(1, "get_weather", {}, "", True, "b", 2),
           TraceEntry(2, "calculator", {}, "", True, "c", 1)]
    seq = [TraceEntry(1, "get_weather", {}, "", True, "a", 1), TraceEntry(2, "get_weather", {}, "", True, "b", 1)]
    assert tool_score(par, task) == 1.0
    assert tool_score(seq, task) == pytest.approx(0.25)


def test_practice_tasks_are_well_formed():
    tasks = load_tasks()
    assert 12 <= len(tasks) <= 15
    names = {t.name for t in default_tools("/nonexistent/notes.json")}
    for t in tasks:
        assert set(t["tools"]) <= names, t["id"]
    assert any(t.get("parallel") for t in tasks)
    assert any(t["id"].startswith("error") for t in tasks)
