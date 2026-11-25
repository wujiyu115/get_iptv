import importlib

import pytest

from pipeline.models import Entry, RunCancelled
from pipeline.runner import merge_history


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


def _reload(tmp_path, monkeypatch, cfg=""):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("CONFIG_FILE", str(tmp_path / "cfg.yaml"))
    (tmp_path / "cfg.yaml").write_text(
        f"output:\n  dir: {tmp_path}/out\ncheck:\n  ffprobe_enabled: false\n" + cfg,
        encoding="utf-8")
    import config.config_loader as cl
    importlib.reload(cl)
    import db.database as d
    importlib.reload(d)
    d.init_db()
    import pipeline.fetch as fetch
    import pipeline.runner as runner
    importlib.reload(fetch)
    importlib.reload(runner)
    return d, runner


def test_recheck_history_drops_dead_candidates(monkeypatch):
    """Backfill must not publish URLs blindly: a signed URL from the previous
    run is already expired, so only the survivors may be merged."""
    from pipeline import runner

    cands = [Entry(name="LIVE", url="http://ok/gen.php?id=1", ua="AptvPlayer-UA"),
             Entry(name="DEAD", url="http://x/migu.m3u8?SecurityKey=old")]
    monkeypatch.setattr(
        runner.check_http, "check_all",
        lambda es, **k: [e for e in es if "SecurityKey" not in e.url])
    monkeypatch.setattr(runner.check_ffprobe, "check_all", lambda es, **k: es)

    logs = []
    out = runner.recheck_history(cands, lambda m, s="": logs.append(m), lambda: False)
    assert [e.name for e in out] == ["LIVE"]
    assert out[0].ua == "AptvPlayer-UA"  # UA survives the recheck
    assert any("1/2 alive" in m for m in logs)


def test_recheck_history_passes_cancel_hook(monkeypatch):
    from pipeline import runner

    seen = {}

    def fake_check(es, **k):
        seen["cancel"] = k.get("should_cancel") is cancel
        return es

    cancel = lambda: False  # noqa: E731
    monkeypatch.setattr(runner.check_http, "check_all", fake_check)
    monkeypatch.setattr(runner.check_ffprobe, "check_all", fake_check)
    runner.recheck_history([Entry(name="A", url="u")], lambda m, s="": None, cancel)
    assert seen["cancel"] is True


def test_run_persists_entry_ua(tmp_path, monkeypatch):
    d, runner = _reload(tmp_path, monkeypatch)
    monkeypatch.setattr(
        runner.fetch, "fetch_all",
        lambda sources, **k: [(({"name": "aptv", "type": "m3u"}),
                               '#EXTM3U\n#EXTINF:-1 http-user-agent="AptvPlayer-UA" '
                               'group-title="央视",CCTV1\n'
                               'http://101.35.240.114:88/live.php?id=CCTV1\n')])
    monkeypatch.setattr(runner.check_http, "check_all", lambda es, **k: es)

    run_id = runner.run()
    conn = d.get_conn()
    row = conn.execute("SELECT ua FROM channels WHERE run_id=? AND name='CCTV1'",
                       (run_id,)).fetchone()
    assert row["ua"] == "AptvPlayer-UA"
    out = (tmp_path / "out" / "full.m3u").read_text(encoding="utf-8")
    assert 'http-user-agent="AptvPlayer-UA"' in out


def test_run_backfill_drops_dead_history_url(tmp_path, monkeypatch):
    """End to end: run 1 publishes OLD, run 2 no longer sources it. The dead
    history URL must not reappear in the playlist."""
    d, runner = _reload(tmp_path, monkeypatch)
    monkeypatch.setattr(
        runner.fetch, "fetch_all",
        lambda sources, **k: [(({"name": "s", "type": "m3u"}),
                               "#EXTM3U\n#EXTINF:-1,OLD\nhttp://dead/old.m3u8\n")])
    monkeypatch.setattr(runner.check_http, "check_all", lambda es, **k: es)
    runner.run()

    monkeypatch.setattr(
        runner.fetch, "fetch_all",
        lambda sources, **k: [(({"name": "s", "type": "m3u"}),
                               "#EXTM3U\n#EXTINF:-1,NEW\nhttp://live/new.m3u8\n")])
    monkeypatch.setattr(
        runner.check_http, "check_all",
        lambda es, **k: [e for e in es if "dead" not in e.url])
    runner.run()

    out = (tmp_path / "out" / "full.m3u").read_text(encoding="utf-8")
    assert "http://live/new.m3u8" in out
    assert "http://dead/old.m3u8" not in out


def test_run_backfill_keeps_history_when_recheck_disabled(tmp_path, monkeypatch):
    """The toggle restores the old blind-backfill behaviour for anyone who
    prefers stability over freshness."""
    d, runner = _reload(tmp_path, monkeypatch, "\nfilter:\n  history_recheck: false\n")
    monkeypatch.setattr(
        runner.fetch, "fetch_all",
        lambda sources, **k: [(({"name": "s", "type": "m3u"}),
                               "#EXTM3U\n#EXTINF:-1,OLD\nhttp://dead/old.m3u8\n")])
    monkeypatch.setattr(runner.check_http, "check_all", lambda es, **k: es)
    runner.run()

    monkeypatch.setattr(
        runner.fetch, "fetch_all",
        lambda sources, **k: [(({"name": "s", "type": "m3u"}),
                               "#EXTM3U\n#EXTINF:-1,NEW\nhttp://live/new.m3u8\n")])
    monkeypatch.setattr(
        runner.check_http, "check_all",
        lambda es, **k: [e for e in es if "dead" not in e.url])
    runner.run()

    out = (tmp_path / "out" / "full.m3u").read_text(encoding="utf-8")
    assert "http://dead/old.m3u8" in out


def test_run_backfill_carries_ua(tmp_path, monkeypatch):
    """A backfilled channel keeps its UA; without it the recheck itself 404s
    and the entry is lost."""
    d, runner = _reload(tmp_path, monkeypatch)
    seen = []

    monkeypatch.setattr(
        runner.fetch, "fetch_all",
        lambda sources, **k: [(({"name": "aptv", "type": "m3u"}),
                               '#EXTM3U\n#EXTINF:-1 http-user-agent="AptvPlayer-UA",'
                               'CCTV1\nhttp://h/live.php?id=CCTV1\n')])

    def fake_check(es, **k):
        seen.extend((e.name, e.ua) for e in es)
        return es

    monkeypatch.setattr(runner.check_http, "check_all", fake_check)
    runner.run()

    seen.clear()
    monkeypatch.setattr(
        runner.fetch, "fetch_all",
        lambda sources, **k: [(({"name": "s", "type": "m3u"}),
                               "#EXTM3U\n#EXTINF:-1,NEW\nhttp://live/new.m3u8\n")])
    runner.run()
    assert ("CCTV1", "AptvPlayer-UA") in seen


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


def test_run_cancelled_marks_status(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("CONFIG_FILE", str(tmp_path / "cfg.yaml"))
    (tmp_path / "cfg.yaml").write_text(
        f"output:\n  dir: {tmp_path}/out\ncheck:\n  ffprobe_enabled: false\n",
        encoding="utf-8")
    import config.config_loader as cl
    importlib.reload(cl)
    import db.database as d
    importlib.reload(d)
    d.init_db()
    import pipeline.fetch as fetch
    import pipeline.runner as runner
    importlib.reload(fetch)
    importlib.reload(runner)

    monkeypatch.setattr(runner.fetch, "fetch_all",
                        lambda sources, **k: [({"name": "s", "type": "m3u"},
                                               "#EXTM3U\n#EXTINF:-1,A\nhttp://a/1\n")])

    # cancel requested immediately -> first checkpoint (after fetch) aborts.
    with pytest.raises(RunCancelled):
        runner.run(on_event=lambda msg, stage="": None, should_cancel=lambda: True)

    conn = d.get_conn()
    row = conn.execute("SELECT status FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    assert row["status"] == "cancelled"
    # a cancelled run must not have written output
    assert not (tmp_path / "out" / "full.m3u").exists()


def test_run_applies_blocked_hosts(tmp_path, monkeypatch):
    """人工确认串播的 (频道, 主机) 必须在上游探测之前就踢掉，并且日志说清理由。"""
    d, runner = _reload(
        tmp_path, monkeypatch,
        "\nfilter:\n  blocked_hosts:\n    CCTV5:\n"
        "      183.250.156.180: 实测串播 CCTV6\n")
    monkeypatch.setattr(
        runner.fetch, "fetch_all",
        lambda sources, **k: [(({"name": "s", "type": "m3u"}),
                               "#EXTM3U\n"
                               "#EXTINF:-1,CCTV5\nhttp://183.250.156.180:8080/c5.m3u8\n"
                               "#EXTINF:-1,CCTV5\nhttp://good.host/c5.m3u8\n")])
    seen = []

    def fake_http(es, **k):
        seen.extend(e.url for e in es)
        return es

    monkeypatch.setattr(runner.check_http, "check_all", fake_http)

    logs = []
    runner.run(on_event=lambda msg, stage="": logs.append(msg))
    out = (tmp_path / "out" / "full.m3u").read_text(encoding="utf-8")
    assert "183.250.156.180" not in out
    assert "good.host/c5.m3u8" in out
    assert "183.250.156.180" not in seen  # 连探测都不该探
    assert any("排除 1 条" in m for m in logs)
    assert any("CCTV5 @ 183.250.156.180 — 实测串播 CCTV6" in m for m in logs)


def test_run_blocked_hosts_also_drops_backfill(tmp_path, monkeypatch):
    """规则可能是运行后才加的：只能靠历史回填的频道也必须被规则拦住，
    否则「唯一能播的那条正好是串播源」的频道会被每一轮复活。"""
    d, runner = _reload(tmp_path, monkeypatch)
    monkeypatch.setattr(
        runner.fetch, "fetch_all",
        lambda sources, **k: [(({"name": "s", "type": "m3u"}),
                               "#EXTM3U\n#EXTINF:-1,CCTV5\n"
                               "http://183.250.156.180:8080/c5.m3u8\n")])
    monkeypatch.setattr(runner.check_http, "check_all", lambda es, **k: es)
    runner.run()
    assert "183.250.156.180" in (tmp_path / "out" / "full.m3u").read_text(encoding="utf-8")

    # 第二轮：加上规则，并且上游不再提供 CCTV5 —— 回填路径同样必须过滤
    d2, runner2 = _reload(
        tmp_path, monkeypatch,
        "\nfilter:\n  blocked_hosts:\n    CCTV5:\n      - 183.250.156.180\n"
        "\n  history_recheck: false\n")
    monkeypatch.setattr(
        runner2.fetch, "fetch_all",
        lambda sources, **k: [(({"name": "s", "type": "m3u"}),
                               "#EXTM3U\n#EXTINF:-1,NEW\nhttp://live/new.m3u8\n")])
    monkeypatch.setattr(runner2.check_http, "check_all", lambda es, **k: es)
    runner2.run()
    out = (tmp_path / "out" / "full.m3u").read_text(encoding="utf-8")
    assert "http://live/new.m3u8" in out
    assert "183.250.156.180" not in out


def test_run_segment_probe_is_off_by_default(tmp_path, monkeypatch):
    """首分片粗筛默认关闭：默认配置下不发额外请求，也不参与过滤。"""
    d, runner = _reload(tmp_path, monkeypatch)
    monkeypatch.setattr(
        runner.fetch, "fetch_all",
        lambda sources, **k: [(({"name": "s", "type": "m3u"}),
                               "#EXTM3U\n#EXTINF:-1,A\nhttp://a.host/v.m3u8\n")])
    monkeypatch.setattr(runner.check_http, "check_all", lambda es, **k: es)
    calls = {}

    def fake_seg(es, **k):
        calls["enabled"] = k.get("enabled")
        return es

    monkeypatch.setattr(runner.check_segment, "check_all", fake_seg)
    logs = []
    runner.run(on_event=lambda msg, stage="": logs.append((msg, stage)))
    assert calls["enabled"] is False
    assert any(stage == "check_segment" for _, stage in logs)
    assert "a.host/v.m3u8" in (tmp_path / "out" / "full.m3u").read_text(encoding="utf-8")


def test_run_segment_probe_feeds_min_seg_kb(tmp_path, monkeypatch):
    """打开后：测到的 seg_kb 进 filter.min_seg_kb，拉不动首分片的线路被剔除。"""
    d, runner = _reload(
        tmp_path, monkeypatch,
        "  segment_probe: true\nfilter:\n  min_seg_kb: 80\n  open_history: false\n")
    monkeypatch.setattr(
        runner.fetch, "fetch_all",
        lambda sources, **k: [(({"name": "s", "type": "m3u"}),
                               "#EXTM3U\n#EXTINF:-1,SLOW\nhttp://slow.host/v.m3u8\n")])
    monkeypatch.setattr(runner.check_http, "check_all", lambda es, **k: es)

    def fake_seg(es, **k):
        for e in es:
            e.seg_kb = 40  # 5 秒内只拿到 40KB：慢线
        return es

    monkeypatch.setattr(runner.check_segment, "check_all", fake_seg)
    runner.run()
    out = (tmp_path / "out" / "full.m3u").read_text(encoding="utf-8")
    assert "slow.host" not in out
