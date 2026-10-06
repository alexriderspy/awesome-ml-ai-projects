from shop.fees import shipping_fee


def test_standard():
    assert shipping_fee(20) == 4.99
    assert shipping_fee(50) == 0.0


def test_express_adds_surcharge():
    assert shipping_fee(20, express=True) == 14.99
    assert shipping_fee(80, express=True) == 10.0
