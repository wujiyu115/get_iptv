import json
import os
from datetime import datetime, timezone

from config.config_loader import config
from db import database
from pipeline import (check_ffprobe, check_http, dedup, fetch, filter_sort,
                      normalize, output, parse)
from pipeline.models import Entry, RunCancelled
from services import settings_service

FAIL_DISABLE_THRESHOLD = 5


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def merge_history(current: list[Entry], previous: list[Entry]) -> list[Entry]:
    if not previous:
        return current
    have = {e.name for e in current}
    out = list(current)
    for e in previous:
        if e.name not in have:
            out.append(e)
    return out


def _load_prev_channels(conn) -> list[Entry]:
    row = conn.execute(
        "SELECT id FROM runs WHERE status='done' ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return []
    rows = conn.execute(
        "SELECT name,group_title,url,logo,tvg_id,tvg_name,source,resolution,speed,delay "
        "FROM channels WHERE run_id=?", (row["id"],)).fetchall()
    return [Entry(name=r["name"], url=r["url"], group=r["group_title"], logo=r["logo"],
                  tvg_id=r["tvg_id"], tvg_name=r["tvg_name"], source=r["source"],
                  resolution=r["resolution"], speed=r["speed"], delay=r["delay"])
            for r in rows]


def run(*, on_event=None, should_cancel=None) -> int:
    emit = on_event or (lambda msg, stage="": None)
    should_cancel = should_cancel or (lambda: False)

    def ckpt() -> None:
        if should_cancel():
            raise RunCancelled()

    conn = database.get_conn()
    cur = conn.execute("INSERT INTO runs(started_at,status) VALUES (?, 'running')",
                       (_now(),))
    run_id = cur.lastrowid
    conn.commit()
    try:
        sources = [dict(r) for r in conn.execute(
            "SELECT * FROM sources WHERE enabled=1 ORDER BY sort, id").fetchall()]
        aliases = [dict(r) for r in conn.execute(
            "SELECT canonical,pattern,is_regex FROM aliases WHERE enabled=1").fetchall()]
        templates = [dict(r) for r in conn.execute(
            "SELECT canonical,group_title,logo,sort FROM templates WHERE enabled=1 "
            "ORDER BY sort").fetchall()]

        emit("stage: fetch", "fetch")
        fetched = fetch.fetch_all(
            sources, user_agent=config.get("fetch.user_agent", ""),
            timeout=config.get("fetch.request_timeout", 10),
            retries=config.get("fetch.retries", 2),
            http_proxy=settings_service.get("fetch.http_proxy", ""),
            on_log=lambda m: emit(m, "fetch"))
        ok_names = {s["name"] for s, _ in fetched}

        ckpt()
        emit("stage: parse", "parse")
        entries: list[Entry] = []
        epg_urls: list[str] = []
        for src, text in fetched:
            entries.extend(parse.parse(text, src["type"], source=src["name"]))
            epg_urls.extend(parse.extract_epg(text))
        epg_urls = list(dict.fromkeys(epg_urls))

        ckpt()
        emit("stage: normalize", "normalize")
        entries = normalize.apply_aliases(entries, aliases)
        entries = normalize.apply_templates(entries, templates, keep_unmatched=True)

        emit("stage: dedup", "dedup")
        entries = dedup.dedup(entries)

        ckpt()
        emit("stage: check_http", "check_http")
        entries = check_http.check_all(
            entries, timeout=config.get("check.http_timeout", 6),
            workers=config.get("check.http_workers", 70),
            open_filter_ad=config.get("filter.open_filter_ad", True),
            on_log=lambda m: emit(m, "check_http"), should_cancel=should_cancel)

        ckpt()
        emit("stage: check_ffprobe", "check_ffprobe")
        entries = check_ffprobe.check_all(
            entries, timeout=config.get("check.ffprobe_timeout", 10),
            workers=config.get("check.ffprobe_workers", 25),
            enabled=config.get("check.ffprobe_enabled", True),
            on_log=lambda m: emit(m, "check_ffprobe"), should_cancel=should_cancel)

        ckpt()
        emit("stage: filter_sort", "filter_sort")
        entries = filter_sort.apply(
            entries, min_resolution=config.get("filter.min_resolution", ""),
            min_speed=config.get("filter.min_speed", 0.0),
            sort_by=config.get("filter.sort_by", "resolution,speed"),
            urls_limit=config.get("filter.urls_limit", 0))

        if config.get("filter.open_history", True):
            emit("stage: history merge", "history")
            entries = merge_history(entries, _load_prev_channels(conn))

        emit("stage: output", "output")
        out_dir = os.environ.get("OUTPUT_DIR") or config.get("output.dir", "./output")
        conn.executemany(
            "INSERT INTO channels(run_id,name,group_title,url,logo,tvg_id,tvg_name,"
            "source,status,detail,resolution,speed,delay) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(run_id, e.name, e.group, e.url, e.logo, e.tvg_id, e.tvg_name, e.source,
              e.status or "ok", e.detail, e.resolution, e.speed, e.delay)
             for e in entries])
        output.write_all(entries, out_dir, epg_urls=epg_urls,
                         open_epg=config.get("output.open_epg", True),
                         open_url_info=config.get("output.open_url_info", False))

        emit("stage: source auto-disable", "sources")
        present_sources = {e.source for e in entries}
        for src in sources:
            if src["name"] in ok_names and src["name"] in present_sources:
                conn.execute("UPDATE sources SET fail_count=0, last_ok_at=? WHERE id=?",
                            (_now(), src["id"]))
            else:
                fc = src["fail_count"] + 1
                enabled = 0 if fc >= FAIL_DISABLE_THRESHOLD else 1
                conn.execute("UPDATE sources SET fail_count=?, enabled=? WHERE id=?",
                            (fc, enabled, src["id"]))

        stats = {"channels": len(entries),
                 "groups": len({e.group for e in entries}),
                 "sources_ok": len(ok_names)}
        conn.execute("UPDATE runs SET status='done', finished_at=?, stats_json=? WHERE id=?",
                    (_now(), json.dumps(stats, ensure_ascii=False), run_id))
        conn.commit()
        emit(f"done: {stats}", "done")
        return run_id
    except RunCancelled:
        # 'cancelled' may violate an older DB's CHECK constraint; fall back to 'failed'.
        try:
            conn.execute("UPDATE runs SET status='cancelled', finished_at=? WHERE id=?",
                        (_now(), run_id))
        except Exception:  # noqa: BLE001
            conn.execute("UPDATE runs SET status='failed', finished_at=? WHERE id=?",
                        (_now(), run_id))
        conn.commit()
        emit("run cancelled by user", "cancelled")
        raise
    except Exception as e:  # noqa: BLE001
        conn.execute("UPDATE runs SET status='failed', finished_at=? WHERE id=?",
                    (_now(), run_id))
        conn.commit()
        emit(f"FAILED: {e}", "failed")
        raise
    finally:
        conn.close()
