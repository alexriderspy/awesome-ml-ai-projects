def to_cents(amount):
    return int(round(amount * 100))


def split_bill(total, people):
    cents = to_cents(total)
    base, extra = divmod(cents, people)
    return [(base + (1 if i < extra else 0)) / 100 for i in range(people)]
