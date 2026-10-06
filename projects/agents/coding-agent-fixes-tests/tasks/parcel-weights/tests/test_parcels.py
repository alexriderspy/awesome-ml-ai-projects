import pytest

from parcels.shipping import parcel_class
from parcels.units import to_grams


def test_units():
    assert to_grams(1, "kg") == 1000
    assert to_grams(2, "lb") == pytest.approx(907.184)
    with pytest.raises(ValueError):
        to_grams(1, "stone")


def test_classes():
    assert parcel_class([(1.5, "kg")]) == "small"
    assert parcel_class([(1, "kg"), (900, "g"), (5, "oz")]) == "medium"
    assert parcel_class([(3, "lb"), (500, "g")]) == "small"
    assert parcel_class([(9, "kg"), (3, "lb")]) == "large"
