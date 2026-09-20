import sqlite3
from datetime import datetime, timezone


class DisruptionError(ValueError):
    """登记中断未通过校验，调用方应转为 4xx；此时库里不得留下生效中断。"""


def _canonical(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((a.strip(), b.strip())))


def _row(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["active"] = bool(d["active"])
    return d


def list_all(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM edge_disruptions ORDER BY id DESC"
    ).fetchall()
    return [_row(r) for r in rows]


def list_active(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM edge_disruptions WHERE active=1 ORDER BY id"
    ).fetchall()
    return [_row(r) for r in rows]


def active_pairs(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """生效中断的邻接边（编码已归一化），用于把边从最短路中剔除。"""
    return [(r["a"], r["b"]) for r in conn.execute(
        "SELECT a,b FROM edge_disruptions WHERE active=1"
    ).fetchall()]


def _edge_exists(conn: sqlite3.Connection, a: str, b: str) -> bool:
    # 无向：两种方向都算同一条邻接边
    row = conn.execute(
        "SELECT 1 FROM edges WHERE (a=? AND b=?) OR (a=? AND b=?) LIMIT 1",
        (a, b, b, a),
    ).fetchone()
    return row is not None


def _station_exists(conn: sqlite3.Connection, code: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM stations WHERE code=? LIMIT 1", (code,)
    ).fetchone() is not None


def create(
    conn: sqlite3.Connection, a: str, b: str, reason: str, active: bool = True
) -> dict:
    """登记一条邻接边中断。校验失败或写入失败一律回滚，绝不残留生效中断。"""
    ca, cb = _canonical(a, b)
    if not ca or not cb or ca == cb:
        raise DisruptionError("两端编码必须是两个不同的站点编码")
    if not _station_exists(conn, ca) or not _station_exists(conn, cb):
        raise DisruptionError(f"站点不存在: {ca} 或 {cb}")
    if not _edge_exists(conn, ca, cb):
        raise DisruptionError(f"{ca}—{cb} 不是一条邻接边，无法登记区间中断")

    # 全部校验先于 INSERT；写库出错再 rollback，双保险保证失败不留生效中断。
    # （同一邻接边的生效中断还受部分唯一索引约束）
    try:
        cur = conn.execute(
            "INSERT INTO edge_disruptions(a,b,reason,active,created_at,released_at)"
            " VALUES (?,?,?,?,?,?)",
            (ca, cb, reason.strip(), 1 if active else 0,
             datetime.now(timezone.utc).isoformat(), None),
        )
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.rollback()
        raise DisruptionError(f"该邻接边已有生效中断: {ca}—{cb}") from e
    except Exception:
        conn.rollback()
        raise

    row = conn.execute("SELECT * FROM edge_disruptions WHERE id=?", (cur.lastrowid,)).fetchone()
    return _row(row)


def release(conn: sqlite3.Connection, disruption_id: int) -> dict | None:
    """解除中断：active 置 0；已解除或不存在返回 None。不触碰任何试算记录。"""
    row = conn.execute(
        "SELECT * FROM edge_disruptions WHERE id=?", (disruption_id,)
    ).fetchone()
    if row is None:
        return None
    if not row["active"]:
        return _row(row)
    conn.execute(
        "UPDATE edge_disruptions SET active=0, released_at=? WHERE id=? AND active=1",
        (datetime.now(timezone.utc).isoformat(), disruption_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM edge_disruptions WHERE id=?", (disruption_id,)).fetchone()
    return _row(row)
