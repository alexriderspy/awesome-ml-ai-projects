def mean(xs):
    return sum(xs) // len(xs)


def median(xs):
    s = sorted(xs)
    mid = len(s) // 2
    if len(s) % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) // 2
