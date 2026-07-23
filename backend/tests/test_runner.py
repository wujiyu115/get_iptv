import importlib

from pipeline.models import Entry
from pipeline.runner import merge_history, FAIL_DISABLE_THRESHOLD


def test_merge_history_backfills_missing_channels():
    current = [Entry(name="CCTV1", url="new1")]
    previous = [Entry(name="CCTV1", url="old1"), Entry(name="CCTV2", url="old2")]
    out = merge_history(current, previous)
    names = {e.name for e in out}
    assert names == {"CCTV1", "CCTV2"}
    cctv1 = [e.url for e in out if e.name == "CCTV1"]
    assert "new1" in cctv1  # current 优先保留


def test_merge_history_no_previous():
    current = [Entry(name="A", url="u")]
    assert merge_history(current, []) == current


def test_run_end_to_end_stubbed(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("CONFIG_FILE", str(tmp_path / "cfg.yaml"))
    (tmp_path / "cfg.yaml").write_text(
        f"output:\n  dir: {tmp_path}/out\ncheck:\n  ffprobe_enabled: false\n",
        encoding="utf-8")
    # config is a module-level singleton created at import time; reload it so the
    # temp CONFIG_FILE (output.dir + ffprobe_enabled) is picked up (see test_config.py).
    import config.config_loader as cl
    importlib.reload(cl)
    import db.database as d
    importlib.reload(d)
    d.init_db()
    import pipeline.fetch as fetch
    import pipeline.runner as runner
    importlib.reload(fetch)
    importlib.reload(runner)

    def fake_fetch_all(sources, **k):
        return [({"name": "s", "type": "m3u"},
                 "#EXTM3U\n#EXTINF:-1 group-title=\"央视\",CCTV1\nhttp://a/1\n")]
    monkeypatch.setattr(runner.fetch, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(runner.check_http, "check_all", lambda es, **k: es)

    logs = []
    run_id = runner.run(on_event=lambda msg, stage="": logs.append(msg))
    conn = d.get_conn()
    row = conn.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()
    assert row["status"] == "done"
    assert conn.execute("SELECT COUNT(*) c FROM channels WHERE run_id=?",
                        (run_id,)).fetchone()["c"] >= 1
    assert (tmp_path / "out" / "full.m3u").exists()
