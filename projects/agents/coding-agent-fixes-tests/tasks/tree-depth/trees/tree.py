def depth(node):
    if not node["children"]:
        return 0
    return 1 + max(depth(child) for child in node["children"])


def count_nodes(node):
    if node is None:
        return 0
    return 1 + sum(count_nodes(c) for c in node["children"])
