UNITS: dict[str, tuple[str, float]] = {
    "m": ("length", 1.0), "km": ("length", 1000.0), "cm": ("length", 0.01), "mm": ("length", 0.001),
    "in": ("length", 0.0254), "ft": ("length", 0.3048), "yd": ("length", 0.9144),
    "mi": ("length", 1609.344), "nmi": ("length", 1852.0),
    "kg": ("mass", 1.0), "g": ("mass", 0.001), "mg": ("mass", 1e-6), "t": ("mass", 1000.0),
    "lb": ("mass", 0.45359237), "oz": ("mass", 0.45359237 / 16), "st": ("mass", 0.45359237 * 14),
    "l": ("volume", 1.0), "ml": ("volume", 0.001), "m3": ("volume", 1000.0),
    "gal": ("volume", 3.785411784), "qt": ("volume", 3.785411784 / 4), "pt": ("volume", 3.785411784 / 8),
    "cup": ("volume", 3.785411784 / 16), "floz": ("volume", 3.785411784 / 128),
    "tbsp": ("volume", 3.785411784 / 256), "tsp": ("volume", 3.785411784 / 768),
    "imp_gal": ("volume", 4.54609),
    "c": ("temperature", 0.0), "f": ("temperature", 0.0), "k": ("temperature", 0.0),
}

ALIASES = {
    "meter": "m", "metre": "m", "meters": "m", "metres": "m",
    "kilometer": "km", "kilometre": "km", "kilometers": "km", "kilometres": "km",
    "centimeter": "cm", "centimetre": "cm", "centimeters": "cm", "centimetres": "cm",
    "millimeter": "mm", "millimetre": "mm", "millimeters": "mm", "millimetres": "mm",
    "inch": "in", "inches": "in", "foot": "ft", "feet": "ft", "yard": "yd", "yards": "yd",
    "mile": "mi", "miles": "mi", "nautical mile": "nmi", "nautical miles": "nmi",
    "kilogram": "kg", "kilograms": "kg", "kgs": "kg", "gram": "g", "grams": "g",
    "milligram": "mg", "milligrams": "mg", "tonne": "t", "tonnes": "t", "metric ton": "t",
    "pound": "lb", "pounds": "lb", "lbs": "lb", "ounce": "oz", "ounces": "oz", "stone": "st",
    "liter": "l", "litre": "l", "liters": "l", "litres": "l", "milliliter": "ml", "millilitre": "ml",
    "milliliters": "ml", "millilitres": "ml", "cubic meter": "m3", "cubic metre": "m3",
    "gallon": "gal", "gallons": "gal", "us gallon": "gal", "quart": "qt", "quarts": "qt",
    "pint": "pt", "pints": "pt", "cups": "cup", "us cup": "cup", "us cups": "cup",
    "fl oz": "floz", "fluid ounce": "floz", "fluid ounces": "floz",
    "tablespoon": "tbsp", "tablespoons": "tbsp", "teaspoon": "tsp", "teaspoons": "tsp",
    "imperial gallon": "imp_gal",
    "celsius": "c", "°c": "c", "degc": "c", "fahrenheit": "f", "°f": "f", "degf": "f", "kelvin": "k",
}


class UnitError(ValueError):
    pass


def normalize(unit: str) -> str:
    u = unit.strip().lower()
    u = ALIASES.get(u, u)
    if u not in UNITS:
        raise UnitError(f"unknown unit {unit!r}. Supported: {', '.join(sorted(UNITS))}")
    return u


def to_kelvin(value: float, unit: str) -> float:
    return {"c": value + 273.15, "f": (value - 32) * 5 / 9 + 273.15, "k": value}[unit]


def from_kelvin(value: float, unit: str) -> float:
    return {"c": value - 273.15, "f": (value - 273.15) * 9 / 5 + 32, "k": value}[unit]


def convert(value: float, from_unit: str, to_unit: str) -> float:
    src, dst = normalize(from_unit), normalize(to_unit)
    (dim_a, fa), (dim_b, fb) = UNITS[src], UNITS[dst]
    if dim_a != dim_b:
        raise UnitError(f"cannot convert {dim_a} ({from_unit}) to {dim_b} ({to_unit})")
    if dim_a == "temperature":
        return from_kelvin(to_kelvin(value, src), dst)
    return value * fa / fb
