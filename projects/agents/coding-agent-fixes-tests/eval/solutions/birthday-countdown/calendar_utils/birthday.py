from datetime import date


def _on_year(birthday, year):
    try:
        return birthday.replace(year=year)
    except ValueError:
        return date(year, 2, 28)


def days_until(birthday, today):
    nxt = _on_year(birthday, today.year)
    if nxt < today:
        nxt = _on_year(birthday, today.year + 1)
    return (nxt - today).days
