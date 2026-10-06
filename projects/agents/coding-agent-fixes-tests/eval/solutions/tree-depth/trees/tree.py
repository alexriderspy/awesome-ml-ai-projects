def depth(node):
    if node is None:
        return 0
    return 1 + max((depth(child) for child in node["children"]), default=0)


def count_nodes(node):
    if node is None:
        return 0
    return 1 + sum(count_nodes(c) for c in node["children"])
