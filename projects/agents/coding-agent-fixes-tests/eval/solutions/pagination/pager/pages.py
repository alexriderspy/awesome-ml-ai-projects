def page_count(items, size):
    return (len(items) + size - 1) // size


def get_page(items, number, size):
    start = (number - 1) * size
    return items[start:start + size]
