def page_count(items, size):
    return len(items) // size


def get_page(items, number, size):
    start = number * size
    return items[start:start + size]
