from datetime import date

from calendar_utils.birthday import days_until


def test_same_year():
    assert days_until(date(1990, 8, 10), date(2027, 8, 1)) == 9
    assert days_until(date(1990, 8, 10), date(2027, 8, 10)) == 0


def test_wraps_over_leap_day():
    assert days_until(date(1995, 3, 1), date(2027, 6, 1)) == 274


def test_leap_day_birthday():
    assert days_until(date(2000, 2, 29), date(2027, 2, 1)) == 27
    assert days_until(date(2000, 2, 29), date(2028, 2, 1)) == 28
