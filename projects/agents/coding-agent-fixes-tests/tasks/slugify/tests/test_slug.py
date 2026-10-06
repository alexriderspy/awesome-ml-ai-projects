from blog.slug import slugify


def test_slugify():
    assert slugify("  Hello, World!  ") == "hello-world"
    assert slugify("Python 3.13 -- what's new?") == "python-3-13-what-s-new"
    assert slugify("already-a-slug") == "already-a-slug"
    assert slugify("!!!") == ""
