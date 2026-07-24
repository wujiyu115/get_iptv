import importlib


def _setup(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    import db.database as d
    importlib.reload(d)
    d.init_db()
    import services.source_service as ss
    import services.run_service as rs
    importlib.reload(ss); importlib.reload(rs)
    return ss, rs


def _setup_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    import db.database as d
    importlib.reload(d)
    d.init_db()
    import services.settings_service as st
    importlib.reload(st)
    return st


def test_source_crud(tmp_path, monkeypatch):
    ss, _ = _setup(tmp_path, monkeypatch)
    n0 = len(ss.list_sources())
    sid = ss.create_source({"name": "x", "url": "http://x", "type": "m3u"})
    assert len(ss.list_sources()) == n0 + 1
    ss.update_source(sid, {"enabled": 0})
    assert [s for s in ss.list_sources() if s["id"] == sid][0]["enabled"] == 0
    ss.delete_source(sid)
    assert len(ss.list_sources()) == n0


def test_reenable_source_resets_fail_count(tmp_path, monkeypatch):
    ss = _setup(tmp_path, monkeypatch)[0]
    sid = ss.create_source({"name": "x", "url": "http://x", "type": "m3u"})
    # simulate accumulated failures + auto-disable
    ss.update_source(sid, {"fail_count": 5, "enabled": 0})
    row = [s for s in ss.list_sources() if s["id"] == sid][0]
    assert row["fail_count"] == 5 and row["enabled"] == 0
    # re-enabling clears fail_count so it won't immediately re-trip the threshold
    ss.update_source(sid, {"enabled": 1})
    row = [s for s in ss.list_sources() if s["id"] == sid][0]
    assert row["enabled"] == 1 and row["fail_count"] == 0


def test_disable_source_keeps_fail_count(tmp_path, monkeypatch):
    ss = _setup(tmp_path, monkeypatch)[0]
    sid = ss.create_source({"name": "y", "url": "http://y", "type": "m3u"})
    ss.update_source(sid, {"fail_count": 3})
    ss.update_source(sid, {"enabled": 0})  # disabling must NOT reset the count
    row = [s for s in ss.list_sources() if s["id"] == sid][0]
    assert row["fail_count"] == 3


def test_settings_get_set(tmp_path, monkeypatch):
    st = _setup_settings(tmp_path, monkeypatch)
    assert st.get("fetch.http_proxy", "DEF") == "DEF"  # missing -> default
    st.set("fetch.http_proxy", "http://127.0.0.1:7890")
    assert st.get("fetch.http_proxy") == "http://127.0.0.1:7890"
    st.set("fetch.http_proxy", "")  # upsert overwrites
    assert st.get("fetch.http_proxy", "DEF") == ""


def test_request_cancel_when_idle_returns_false(tmp_path, monkeypatch):
    _, rs = _setup(tmp_path, monkeypatch)
    assert rs.request_cancel() is False


def test_run_lock_mutex(tmp_path, monkeypatch):
    _, rs = _setup(tmp_path, monkeypatch)
    assert rs.try_acquire() is True
    assert rs.try_acquire() is False  # 已占用
    rs.release()
    assert rs.try_acquire() is True
    rs.release()


def test_ring_buffer_and_snapshot(tmp_path, monkeypatch):
    _, rs = _setup(tmp_path, monkeypatch)
    rs.push_log("hello", "fetch")
    snap = rs.snapshot()
    assert snap["stage"] == "fetch"
    assert any("hello" in x for x in snap["logs"])
