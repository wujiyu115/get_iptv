from collections import Counter

from db.database import get_conn


def report() -> dict:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id FROM runs WHERE status='done' ORDER BY id DESC LIMIT 1").fetchone()
        channels = []
        if row:
            channels = [dict(r) for r in conn.execute(
                "SELECT group_title,resolution FROM channels WHERE run_id=?", (row["id"],))]
        groups = Counter(c["group_title"] or "其他" for c in channels)
        buckets = Counter()
        for c in channels:
            h = c["resolution"]
            buckets["1080p+" if h >= 1080 else "720p" if h >= 720
                    else "480p" if h >= 480 else "SD"] += 1
        sources = [dict(r) for r in conn.execute(
            "SELECT id,name,enabled,fail_count,last_ok_at FROM sources ORDER BY sort, id")]
        runs = [dict(r) for r in conn.execute(
            "SELECT id,started_at,finished_at,status,stats_json FROM runs "
            "ORDER BY id DESC LIMIT 20")]
        return {"groups": dict(groups), "resolution": dict(buckets),
                "sources": sources, "runs": runs}
    finally:
        conn.close()
