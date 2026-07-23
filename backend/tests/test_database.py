import importlib


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    import db.database as d
    importlib.reload(d)
    d.init_db()
    return d


def test_tables_created(tmp_path, monkeypatch):
    d = _fresh_db(tmp_path, monkeypatch)
    conn = d.get_conn()
    names = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"sources", "aliases", "templates", "runs", "channels"} <= names


def test_seed_sources_and_aliases(tmp_path, monkeypatch):
    d = _fresh_db(tmp_path, monkeypatch)
    conn = d.get_conn()
    assert conn.execute("SELECT COUNT(*) c FROM sources").fetchone()["c"] == 5
    assert conn.execute("SELECT COUNT(*) c FROM aliases").fetchone()["c"] > 0


def test_seed_idempotent(tmp_path, monkeypatch):
    d = _fresh_db(tmp_path, monkeypatch)
    d.init_db()  # second call must not duplicate
    conn = d.get_conn()
    assert conn.execute("SELECT COUNT(*) c FROM sources").fetchone()["c"] == 5
