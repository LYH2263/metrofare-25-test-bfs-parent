from collections import defaultdict, deque


def shortest_path(edges: list[tuple[str, str]], start: str, end: str) -> list[str] | None:
    """Undirected graph BFS; reconstruct the shortest station-code sequence from
    the parent-pointer map (父指针). Returns [start] for a same-station query,
    None if unreachable."""
    g: dict[str, set[str]] = defaultdict(set)
    for a, b in edges:
        g[a].add(b)
        g[b].add(a)
    parents = {start: None}
    q = deque([start])
    while q:
        cur = q.popleft()
        if cur == end:
            break
        for nxt in g[cur]:
            if nxt not in parents:
                parents[nxt] = cur
                q.append(nxt)
    if end not in parents:
        return None
    seq: list[str] = []
    cur = end
    while cur is not None:
        seq.append(cur)
        cur = parents[cur]
    seq.reverse()
    return seq


def shortest_hops(edges: list[tuple[str, str]], start: str, end: str) -> int | None:
    """Undirected graph BFS hop count; None if unreachable."""
    path = shortest_path(edges, start, end)
    if path is None:
        return None
    return len(path) - 1
