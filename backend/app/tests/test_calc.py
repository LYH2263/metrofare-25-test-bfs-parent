from app.engines.fare_rules import fare_for_hops
from app.engines.graph_bfs import bfs_parents, shortest_hops
from app.engines.route_quote import quote_route

EDGES = [("A1", "A2"), ("A2", "A3"), ("A2", "B1"), ("B1", "B2")]
RULES = [{"max_hops": 2, "price": 3.0}, {"max_hops": 4, "price": 4.0}, {"max_hops": None, "price": 6.0}]

# 编码 -> 站名（与 seed 数据一致）：A1 城站、A2 市心、A3 东湾、B1 北苑、B2 机场
NAMES = {"A1": "城站", "A2": "市心", "A3": "东湾", "B1": "北苑", "B2": "机场"}


def restore_from_parents(edges, start, end):
    """纯函数：从 BFS 父指针回溯还原起点到终点的编码序列，不可达返回 None。"""
    parents = bfs_parents(edges, start)
    if end not in parents:
        return None
    seq = []
    cur = end
    while cur is not None:  # 起点的父指针为 None，回溯到此结束
        seq.append(cur)
        cur = parents[cur]
    seq.reverse()
    return seq


def assert_seq(got, expected):
    assert got == expected, f"得到的序列: {got!r}，期望序列: {expected!r}"


def test_hops_a1_a3():
    assert shortest_hops(EDGES, "A1", "A3") == 2


def test_hops_a1_b2():
    assert shortest_hops(EDGES, "A1", "B2") == 3


def test_path_a1_b2():
    # 城站 -> 市心 -> 北苑 -> 机场
    seq = restore_from_parents(EDGES, "A1", "B2")
    expected = ["A1", "A2", "B1", "B2"]
    assert_seq(seq, expected)
    name_seq = [NAMES[c] for c in seq]
    assert name_seq == ["城站", "市心", "北苑", "机场"], (
        f"得到的站名序列: {name_seq!r}，期望序列: ['城站', '市心', '北苑', '机场']"
    )
    # 站数（hop 数）等于序列长度减一
    assert len(seq) - 1 == 3, f"站数: {len(seq) - 1}，期望: 3"
    assert shortest_hops(EDGES, "A1", "B2") == len(seq) - 1


def test_path_a1_a3():
    # 城站 -> 市心 -> 东湾
    seq = restore_from_parents(EDGES, "A1", "A3")
    expected = ["A1", "A2", "A3"]
    assert_seq(seq, expected)
    assert len(seq) == 3, f"序列长度: {len(seq)}，期望: 3"
    assert shortest_hops(EDGES, "A1", "A3") == len(seq) - 1


def test_path_unreachable_has_no_sequence():
    # C1-C2 是与 A/B 网断开的分量，A1 不可达
    edges = EDGES + [("C1", "C2")]
    seq = restore_from_parents(edges, "A1", "C1")
    assert seq is None, f"不可达不应有序列，得到的序列: {seq!r}，期望序列: None"
    assert shortest_hops(edges, "A1", "C1") is None


def test_path_same_station():
    seq = restore_from_parents(EDGES, "A1", "A1")
    expected = ["A1"]
    assert_seq(seq, expected)
    assert len(seq) - 1 == 0
    assert shortest_hops(EDGES, "A1", "A1") == 0


def test_fare_by_hops():
    assert fare_for_hops(2, RULES) == 3.0
    assert fare_for_hops(3, RULES) == 4.0
    assert fare_for_hops(10, RULES) == 6.0


def test_quote():
    q = quote_route(EDGES, "A1", "B2", RULES)
    assert q["hops"] == 3 and q["fare"] == 4.0
