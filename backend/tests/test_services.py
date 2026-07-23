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


def test_source_crud(tmp_path, monkeypatch):
    ss, _ = _setup(tmp_path, monkeypatch)
    n0 = len(ss.list_sources())
    sid = ss.create_source({"name": "x", "url": "http://x", "type": "m3u"})
    assert len(ss.list_sources()) == n0 + 1
    ss.update_source(sid, {"enabled": 0})
    assert [s for s in ss.list_sources() if s["id"] == sid][0]["enabled"] == 0
    ss.delete_source(sid)
    assert len(ss.list_sources()) == n0


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
