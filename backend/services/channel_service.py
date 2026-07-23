from db.database import get_conn


def _latest_done_run_id(conn):
    row = conn.execute(
        "SELECT id FROM runs WHERE status='done' ORDER BY id DESC LIMIT 1").fetchone()
    return row["id"] if row else None


def list_channels(run: str = "latest") -> list[dict]:
    conn = get_conn()
    try:
        rid = _latest_done_run_id(conn) if run == "latest" else int(run)
        if rid is None:
            return []
        return [dict(r) for r in conn.execute(
            "SELECT * FROM channels WHERE run_id=? ORDER BY group_title, name", (rid,))]
    finally:
        conn.close()
