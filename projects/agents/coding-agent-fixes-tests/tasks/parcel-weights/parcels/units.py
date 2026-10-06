GRAMS_PER = {"g": 1, "kg": 100, "oz": 28.3495}


def to_grams(value, unit):
    try:
        return value * GRAMS_PER[unit]
    except KeyError:
        raise ValueError(f"unknown unit: {unit}") from None
