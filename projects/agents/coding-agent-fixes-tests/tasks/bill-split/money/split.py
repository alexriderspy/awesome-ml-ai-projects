def to_cents(amount):
    return int(amount * 100)


def split_bill(total, people):
    cents = to_cents(total)
    share = round(cents / people)
    return [share / 100 for _ in range(people)]
