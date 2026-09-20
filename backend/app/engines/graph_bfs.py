from collections import defaultdict, deque


def bfs_parents(edges: list[tuple[str, str]], start: str) -> dict[str, str | None]:
    """Breadth-first search returning a parent-pointer map.

    parents[start] is None; every reached node maps to the node via which
    it was first discovered. An unreached node is simply absent from the
    map (walk the chain from a target back to ``start`` to restore the path).
    """
    g: dict[str, set[str]] = defaultdict(set)
    for a, b in edges:
        g[a].add(b)
        g[b].add(a)
    parents: dict[str, str | None] = {start: None}
    q = deque([start])
    while q:
        cur = q.popleft()
        for nxt in g[cur]:
            if nxt not in parents:
                parents[nxt] = cur
                q.append(nxt)
    return parents


def restore_path(parents: dict[str, str | None], start: str, end: str) -> list[str] | None:
    """Walk parent pointers from ``end`` back to ``start``; None if unreachable."""
    if end not in parents:
        return None
    path: list[str] = []
    cur: str | None = end
    while cur is not None:
        path.append(cur)
        cur = parents[cur]
    path.reverse()
    if not path or path[0] != start:
        return None
    return path


def shortest_path(edges: list[tuple[str, str]], start: str, end: str) -> list[str] | None:
    """Undirected graph BFS shortest station sequence; None if unreachable."""
    return restore_path(bfs_parents(edges, start), start, end)


def shortest_hops(edges: list[tuple[str, str]], start: str, end: str) -> int | None:
    """Undirected graph BFS hop count; None if unreachable."""
    path = shortest_path(edges, start, end)
    if path is None:
        return None
    return len(path) - 1
