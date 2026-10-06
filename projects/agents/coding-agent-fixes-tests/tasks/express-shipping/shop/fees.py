FREE_SHIPPING_FROM = 50.00
STANDARD_FEE = 4.99
EXPRESS_SURCHARGE = 10.00


def shipping_fee(subtotal, express=False):
    fee = 0.0 if subtotal >= FREE_SHIPPING_FROM else STANDARD_FEE
    if express:
        fee = fee * EXPRESS_SURCHARGE
    return round(fee, 2)
