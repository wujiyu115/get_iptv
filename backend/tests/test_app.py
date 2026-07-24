import importlib


def _client_with_frontend(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    (dist / "static").mkdir(parents=True)
    (dist / "index.html").write_text("<html>spa</html>", encoding="utf-8")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("FRONTEND", str(dist))
    # These tests only exercise SPA/static routing. Neutralize the scheduler so
    # create_app() does not fire a real startup pipeline run (network + DB) or
    # leave a live BackgroundScheduler thread. Test-only; real behavior intact.
    import scheduler.scheduler as sched
    monkeypatch.setattr(sched, "start", lambda: None)
    import db.database as d
    importlib.reload(d)
    d.init_db()
    import app as appmod
    importlib.reload(appmod)
    from fastapi.testclient import TestClient
    return TestClient(appmod.app)


def test_spa_fallback_serves_index(tmp_path, monkeypatch):
    c = _client_with_frontend(tmp_path, monkeypatch)
    r = c.get("/some/frontend/route")
    assert r.status_code == 200 and "spa" in r.text


def test_unknown_api_under_catchall_is_404(tmp_path, monkeypatch):
    c = _client_with_frontend(tmp_path, monkeypatch)
    assert c.get("/api/does-not-exist").status_code == 404


def test_path_traversal_blocked(tmp_path, monkeypatch):
    c = _client_with_frontend(tmp_path, monkeypatch)
    # httpx normalizes a literal "/../secret" to "/secret" client-side before it
    # is ever sent, so it never reaches the server-side guard. Use a percent-
    # encoded ".." so the raw traversal actually reaches the catch-all guard.
    assert c.get("/%2e%2e/secret").status_code in (403, 404)
