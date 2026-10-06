import os
from pathlib import Path
from typing import Callable

from .calculator import evaluate, format_number
from .notes import NotesStore
from .schema import Tool, tool
from .units import convert
from .weather import current_weather


@tool
def calculator(expression: str) -> str:
    """Evaluate an arithmetic expression exactly. Use this for any maths instead of computing in your head.

    Args:
        expression: Arithmetic using + - * / // % ** and parentheses, plus sqrt, abs, round, min, max, log, log10, exp, sin, cos, tan, floor, ceil, pi, e. Example: (12.5 * 4) / sqrt(16)
    """
    return format_number(evaluate(expression))


@tool
def unit_convert(value: float, from_unit: str, to_unit: str) -> str:
    """Convert a quantity between units of length, mass, volume or temperature.

    Args:
        value: The number to convert.
        from_unit: Source unit, for example km, mi, ft, in, kg, lb, oz, st, l, ml, gal, cup, tbsp, c, f, k.
        to_unit: Target unit of the same kind (length, mass, volume or temperature).
    """
    result = convert(value, from_unit, to_unit)
    return f"{format_number(value)} {from_unit} = {format_number(round(result, 6))} {to_unit}"


def make_weather_tool(fetch: Callable[[str], dict] = current_weather) -> Tool:

    @tool(name="get_weather")
    def get_weather(city: str) -> dict:
        """Get the current weather (temperature in Celsius, humidity, wind, conditions) for a city.

        Args:
            city: City name, for example "Lisbon" or "Pune".
        """
        return fetch(city)

    return get_weather


def make_notes_tools(store: NotesStore) -> list[Tool]:

    @tool
    def add_note(text: str, tags: list[str] | None = None) -> dict:
        """Save a new note for the user.

        Args:
            text: The note text.
            tags: Optional short tags, for example ["shopping"].
        """
        return {"saved": store.add(text, tags)}

    @tool
    def list_notes(limit: int = 20) -> list[dict]:
        """List the user's most recent notes.

        Args:
            limit: How many notes to return, newest last.
        """
        return store.all()[-limit:]

    @tool
    def search_notes(query: str) -> list[dict]:
        """Search the user's notes by keywords. Returns matching notes, best match first.

        Args:
            query: Keywords to look for, for example "dentist".
        """
        return store.search(query)

    return [add_note, list_notes, search_notes]


def default_tools(notes_path: str | Path | None = None,
                  weather_fetch: Callable[[str], dict] = current_weather) -> list[Tool]:
    notes_path = notes_path or os.getenv("NOTES_PATH", "notes.json")
    return [calculator, unit_convert, make_weather_tool(weather_fetch), *make_notes_tools(NotesStore(notes_path))]

