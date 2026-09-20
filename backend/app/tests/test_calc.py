from app.engines.fare_rules import fare_for_hops
from app.engines.graph_bfs import shortest_hops, shortest_path
from app.engines.route_quote import quote_route

EDGES = [("A1", "A2"), ("A2", "A3"), ("A2", "B1"), ("B1", "B2")]
RULES = [{"max_hops": 2, "price": 3.0}, {"max_hops": 4, "price": 4.0}, {"max_hops": None, "price": 6.0}]

# 与种子站点一致的编码 -> 站名（仅用于把编码序列还原为站名序列做断言）
NAMES = {"A1": "城站", "A2": "市心", "A3": "东湾", "B1": "北苑", "B2": "机场"}


def test_hops_a1_a3():
    assert shortest_hops(EDGES, "A1", "A3") == 2


def test_hops_a1_b2():
    assert shortest_hops(EDGES, "A1", "B2") == 3


def test_fare_by_hops():
    assert fare_for_hops(2, RULES) == 3.0
    assert fare_for_hops(3, RULES) == 4.0
    assert fare_for_hops(10, RULES) == 6.0


def test_quote():
    q = quote_route(EDGES, "A1", "B2", RULES)
    assert q["hops"] == 3 and q["fare"] == 4.0


def test_path_sequence_a1_b2():
    """从父指针还原 A1 到 B2 的编码序列：城站 -> 市心 -> 北苑 -> 机场。"""
    expected_codes = ["A1", "A2", "B1", "B2"]
    seq = shortest_path(EDGES, "A1", "B2")
    assert seq == expected_codes, f"编码序列不符: 得到 {seq!r}, 期望 {expected_codes!r}"

    expected_names = ["城站", "市心", "北苑", "机场"]
    names = [NAMES[c] for c in seq]
    assert names == expected_names, f"站名序列不符: 得到 {names!r}, 期望 {expected_names!r}"

    # 站数等于序列长度减一（不得以票价数字代替）
    assert shortest_hops(EDGES, "A1", "B2") == len(seq) - 1

    # 连续两次还原结论相同
    assert shortest_path(EDGES, "A1", "B2") == seq


def test_path_sequence_a1_a3():
    seq = shortest_path(EDGES, "A1", "A3")
    expected = ["A1", "A2", "A3"]
    assert seq == expected, f"编码序列不符: 得到 {seq!r}, 期望 {expected!r}"
    assert len(seq) == 3, f"序列长度不符: 得到 {len(seq)}, 期望 3（序列 {seq!r}）"
    assert shortest_hops(EDGES, "A1", "A3") == len(seq) - 1


def test_path_unreachable_has_no_sequence():
    edges = EDGES + [("C1", "C2")]
    seq = shortest_path(edges, "A1", "C1")
    assert seq is None, f"不可达不应有序列: 得到 {seq!r}, 期望 None"
    assert shortest_hops(edges, "A1", "C1") is None
    # 端点根本不在图中同样不可达
    assert shortest_path(EDGES, "A1", "Z9") is None


def test_path_same_station():
    seq = shortest_path(EDGES, "A1", "A1")
    expected = ["A1"]
    assert seq == expected, f"同站序列不符: 得到 {seq!r}, 期望 {expected!r}"
    assert shortest_hops(EDGES, "A1", "A1") == len(seq) - 1 == 0
