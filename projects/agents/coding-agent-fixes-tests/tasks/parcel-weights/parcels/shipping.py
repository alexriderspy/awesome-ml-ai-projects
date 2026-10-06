from .units import to_grams

SMALL_MAX_G = 2000
MEDIUM_MAX_G = 10000


def parcel_class(items):
    total_kg = sum(to_grams(v, u) for v, u in items)
    if total_kg <= SMALL_MAX_G / 1000:
        return "small"
    if total_kg <= MEDIUM_MAX_G / 1000:
        return "medium"
    return "large"
