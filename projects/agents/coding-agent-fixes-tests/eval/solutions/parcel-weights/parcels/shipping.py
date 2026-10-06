from .units import to_grams

SMALL_MAX_G = 2000
MEDIUM_MAX_G = 10000


def parcel_class(items):
    total_g = sum(to_grams(v, u) for v, u in items)
    if total_g <= SMALL_MAX_G:
        return "small"
    if total_g <= MEDIUM_MAX_G:
        return "medium"
    return "large"
