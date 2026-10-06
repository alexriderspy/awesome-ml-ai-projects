from pager.pages import get_page, page_count

ITEMS = list("abcdefg")


def test_first_page():
    assert get_page(ITEMS, 1, 3) == ["a", "b", "c"]


def test_last_partial_page():
    assert get_page(ITEMS, 3, 3) == ["g"]
    assert get_page(ITEMS, 4, 3) == []


def test_page_count_rounds_up():
    assert page_count(ITEMS, 3) == 3
    assert page_count(ITEMS[:6], 3) == 2
    assert page_count([], 3) == 0
