import importlib

from db.seed import SEED_ALIASES, SEED_SOURCES

N_SEED = len(SEED_SOURCES)


def test_seed_sources_wellformed():
    names = [name for name, _, _ in SEED_SOURCES]
    assert len(names) == len(set(names)), "seed source names must be unique"
    for name, url, kind in SEED_SOURCES:
        assert url.startswith("https://"), (name, url)
        assert kind in ("m3u", "txt"), (name, kind)


def test_seed_aliases_wellformed():
    canonicals = [c for c, _, _ in SEED_ALIASES]
    assert len(canonicals) == len(set(canonicals))
    assert all(p for _, p, _ in SEED_ALIASES)


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
    assert conn.execute("SELECT COUNT(*) c FROM sources").fetchone()["c"] == N_SEED
    assert conn.execute("SELECT COUNT(*) c FROM aliases").fetchone()["c"] > 0


def test_seed_idempotent(tmp_path, monkeypatch):
    d = _fresh_db(tmp_path, monkeypatch)
    d.init_db()  # second call must not duplicate
    conn = d.get_conn()
    assert conn.execute("SELECT COUNT(*) c FROM sources").fetchone()["c"] == N_SEED
