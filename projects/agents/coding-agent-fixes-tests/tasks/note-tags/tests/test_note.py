from notebook.note import Note


def test_tags_are_per_note():
    a = Note("groceries").tag("home")
    b = Note("standup")
    assert a.tags == ["home"]
    assert b.tags == []


def test_caller_list_not_mutated():
    start = ["work"]
    n = Note("plan", start).tag("urgent")
    assert n.tags == ["work", "urgent"]
    assert start == ["work"]
