import importlib


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("FRONTEND", str(tmp_path / "nodist"))  # 无前端，跳过 catch-all
    import db.database as d
    importlib.reload(d)
    d.init_db()
    import app as appmod
    importlib.reload(appmod)
    from fastapi.testclient import TestClient
    return TestClient(appmod.app)


def test_sources_crud_via_api(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert len(c.get("/api/sources").json()) == 5
    rid = c.post("/api/sources", json={"name": "x", "url": "http://x", "type": "m3u"}).json()["id"]
    assert len(c.get("/api/sources").json()) == 6
    c.put(f"/api/sources/{rid}", json={"enabled": 0})
    c.delete(f"/api/sources/{rid}")
    assert len(c.get("/api/sources").json()) == 5


def test_task_status_idle(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.get("/api/tasks/status").json()["status"] in ("idle", "running", "done")


def test_playlist_404_before_generation(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.get("/full.m3u").status_code == 404


def test_reports_shape(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    body = c.get("/api/reports").json()
    assert set(body) == {"groups", "resolution", "sources", "runs"}
