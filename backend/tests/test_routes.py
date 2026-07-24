import importlib

from db.seed import SEED_SOURCES

N_SEED = len(SEED_SOURCES)


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
    assert len(c.get("/api/sources").json()) == N_SEED
    rid = c.post("/api/sources", json={"name": "x", "url": "http://x", "type": "m3u"}).json()["id"]
    assert len(c.get("/api/sources").json()) == N_SEED + 1
    c.put(f"/api/sources/{rid}", json={"enabled": 0})
    c.delete(f"/api/sources/{rid}")
    assert len(c.get("/api/sources").json()) == N_SEED


def test_task_status_idle(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.get("/api/tasks/status").json()["status"] in ("idle", "running", "done")


def test_stop_when_idle_returns_409(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.post("/api/tasks/stop").status_code == 409


def test_source_github_updated_per_id(tmp_path, monkeypatch):
    import services.github_service as gh
    monkeypatch.setattr(gh, "last_updated",
                        lambda url, now=None: "2026-07-24T00:00:00Z"
                        if "raw.githubusercontent.com" in url else None)
    c = _client(tmp_path, monkeypatch)
    ids = [s["id"] for s in c.get("/api/sources").json()]
    body = c.get(f"/api/sources/{ids[0]}/github-updated").json()
    assert body["id"] == ids[0] and "updated" in body


def test_source_github_updated_404(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.get("/api/sources/999999/github-updated").status_code == 404


def test_proxy_setting_roundtrip(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.get("/api/settings/proxy").json() == {"http_proxy": ""}
    assert c.put("/api/settings/proxy",
                 json={"http_proxy": " http://127.0.0.1:7890 "}).status_code == 200
    assert c.get("/api/settings/proxy").json()["http_proxy"] == "http://127.0.0.1:7890"


def test_playlist_404_before_generation(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.get("/full.m3u").status_code == 404


def test_reports_shape(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    body = c.get("/api/reports").json()
    assert set(body) == {"groups", "resolution", "sources", "runs"}
