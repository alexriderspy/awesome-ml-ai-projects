from money.split import split_bill, to_cents


def test_to_cents():
    assert to_cents(0.29) == 29
    assert to_cents(19.99) == 1999


def test_split_exact():
    assert split_bill(100, 3) == [33.34, 33.33, 33.33]
    assert split_bill(10, 4) == [2.5, 2.5, 2.5, 2.5]
    assert split_bill(0.29, 2) == [0.15, 0.14]


def test_shares_add_up():
    shares = split_bill(87.65, 7)
    assert sum(to_cents(s) for s in shares) == 8765
