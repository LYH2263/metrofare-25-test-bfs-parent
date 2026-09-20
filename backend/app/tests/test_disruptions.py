import json

import pytest

import app.db as db_mod
from app import seed
from app.engines.route_quote import quote_route
from app.repositories import disruptions as dr
from app.repositories import runs as rr
from app.services.metro_service import MetroService

# 带直达边的环：A1—A3 直达(1站)，旁路 A1—A2—A3(2站)
LOOP_EDGES = [("A1", "A2"), ("A2", "A3"), ("A1", "A3")]
# 种子树形网络
TREE_EDGES = [("A1", "A2"), ("A2", "A3"), ("A2", "B1"), ("B1", "B2")]
STEP_RULES = [{"max_hops": 1, "price": 2.0}, {"max_hops": None, "price": 4.0}]
TREE_RULES = [{"max_hops": 2, "price": 3.0}, {"max_hops": 4, "price": 4.0}, {"max_hops": None, "price": 6.0}]


@pytest.fixture
def svc(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod, "DB_PATH", tmp_path / "test.db")
    seed.init_db()
    with MetroService() as s:
        yield s


# ---------- 引擎层 ----------

def test_normal_quote_has_path():
    q = quote_route(LOOP_EDGES, "A1", "A3", STEP_RULES)
    assert q["reachable"] is True
    assert q["path"] == ["A1", "A3"]
    assert q["hops"] == 1 and q["fare"] == 2.0
    assert q["detoured"] is False and q["avoided_edges"] == []


def test_detour_gives_new_path_hops_fare_and_names_edge():
    # 直达边中断后须绕行：新途经站、新站数、新票价，并点名绕开了哪条边
    q = quote_route(LOOP_EDGES, "A1", "A3", STEP_RULES, blocked_edges=[("A1", "A3")])
    assert q["reachable"] is True
    assert q["path"] == ["A1", "A2", "A3"]
    assert q["hops"] == 2 and q["fare"] == 4.0
    assert q["detoured"] is True
    assert q["avoided_edges"] == [{"a": "A1", "b": "A3"}]


def test_blocked_edge_direction_normalized():
    # 无向边，反方向登记同样不得进入最短路
    q = quote_route(LOOP_EDGES, "A1", "A3", STEP_RULES, blocked_edges=[("A3", "A1")])
    assert q["path"] == ["A1", "A2", "A3"]
    assert q["avoided_edges"] == [{"a": "A1", "b": "A3"}]


def test_unreachable_names_blocking_edge_and_invents_no_path():
    # 树上去掉桥边 B1—B2，A1 到 B2 不连通
    q = quote_route(TREE_EDGES, "A1", "B2", TREE_RULES, blocked_edges=[("B1", "B2")])
    assert q["reachable"] is False
    assert q["path"] is None          # 不得编造途经站
    assert q["hops"] is None and q["fare"] is None
    assert q["blocked_edges"] == [{"a": "B1", "b": "B2"}]
    assert q["avoided_edges"] == []


def test_unrelated_blocked_edge_leaves_route_intact():
    q = quote_route(TREE_EDGES, "A1", "A3", TREE_RULES, blocked_edges=[("B1", "B2")])
    assert q["path"] == ["A1", "A2", "A3"]
    assert q["detoured"] is False and q["avoided_edges"] == []


def test_release_restores_original_route():
    blocked = quote_route(TREE_EDGES, "A1", "B2", TREE_RULES, blocked_edges=[("B2", "B1")])
    assert blocked["reachable"] is False
    # 解除（不再传屏蔽边）后同一起终点回到中断前的站数、途经站、票价
    restored = quote_route(TREE_EDGES, "A1", "B2", TREE_RULES)
    assert restored["path"] == ["A1", "A2", "B1", "B2"]
    assert restored["hops"] == 3 and restored["fare"] == 4.0


# ---------- 仓储 / 服务层（真实 SQLite） ----------

def _count_active(svc):
    return svc._conn.execute("SELECT COUNT(*) c FROM edge_disruptions WHERE active=1").fetchone()["c"]


def test_create_disruption_takes_effect_and_releases(svc):
    d = svc.create_disruption("B2", "B1", "信号检修")  # 故意反方向录入
    assert d["active"] is True and (d["a"], d["b"]) == ("B1", "B2")
    assert dr.active_pairs(svc._conn) == [("B1", "B2")]

    q = svc.quote("A1", "B2", persist=False)
    assert q["reachable"] is False and q["path"] is None
    assert q["blocked_edges"][0]["a"] == "B1" and q["blocked_edges"][0]["b"] == "B2"
    assert q["blocked_edges"][0]["reason"] == "信号检修"

    assert svc.release_disruption(d["id"])["active"] is False
    q2 = svc.quote("A1", "B2", persist=False)
    assert q2["path"] == ["A1", "A2", "B1", "B2"] and q2["hops"] == 3 and q2["fare"] == 4.0


def test_create_failure_leaves_no_active_disruption(svc):
    # A1—A3 不是邻接边：创建必须失败，且库里不得留下生效中断
    with pytest.raises(dr.DisruptionError):
        svc.create_disruption("A1", "A3", "越站登记")
    assert _count_active(svc) == 0

    with pytest.raises(dr.DisruptionError):
        svc.create_disruption("A1", "ZZ", "端点不存在")
    assert _count_active(svc) == 0


def test_duplicate_active_disruption_rejected(svc):
    svc.create_disruption("A1", "A2", "施工")
    with pytest.raises(dr.DisruptionError):
        svc.create_disruption("A2", "A1", "重复登记")  # 同一条无向边
    assert _count_active(svc) == 1
    # 解除后允许重新登记
    d = svc.disruptions()[0]
    svc.release_disruption(d["id"])
    again = svc.create_disruption("A1", "A2", "二次施工")
    assert again["active"] is True and _count_active(svc) == 1


def test_readonly_trial_does_not_persist(svc):
    before = len(svc.history())
    svc.create_disruption("B1", "B2", "检修")
    out = svc.quote("A1", "B2", persist=False)   # 只读试算：不可达也不落库
    assert out["run_id"] is None and out["reachable"] is False
    assert len(svc.history()) == before


def test_persisted_run_keeps_then_path_after_release(svc):
    # 造一条直达边形成环路
    svc._conn.execute("INSERT INTO edges(a,b) VALUES ('A1','A3')")
    svc._conn.commit()

    svc.create_disruption("A1", "A3", "区间中断")
    detour = svc.quote("A1", "A3", persist=True)   # 中断期间绕行并落库
    assert detour["path"] == ["A1", "A2", "A3"] and detour["hops"] == 2
    run_id = detour["run_id"]
    assert run_id is not None

    d = svc.disruptions()[0]
    svc.release_disruption(d["id"])
    restored = svc.quote("A1", "A3", persist=False)
    assert restored["path"] == ["A1", "A3"] and restored["hops"] == 1

    # 已写入记录保留当时途经站，解除中断不得改写
    row = svc._conn.execute("SELECT result_json FROM calc_runs WHERE id=?", (run_id,)).fetchone()
    snapshot = json.loads(row["result_json"])
    assert snapshot["path"] == ["A1", "A2", "A3"]
    assert snapshot["hops"] == 2
