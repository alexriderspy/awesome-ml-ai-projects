from datetime import date


def days_until(birthday, today):
    this_year = birthday.replace(year=today.year)
    if this_year >= today:
        return (this_year - today).days
    return 365 - (today - this_year).days
