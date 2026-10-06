from trees.tree import count_nodes, depth


def leaf(v):
    return {"value": v, "children": []}


TREE = {"value": 1, "children": [leaf(2), {"value": 3, "children": [leaf(4), {"value": 5, "children": [leaf(6)]}]}]}


def test_depth():
    assert depth(None) == 0
    assert depth(leaf(1)) == 1
    assert depth(TREE) == 4


def test_count():
    assert count_nodes(TREE) == 6
