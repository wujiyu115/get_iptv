import importlib

from db.seed import SEED_ALIASES, SEED_SOURCES

N_SEED = len(SEED_SOURCES)


def test_seed_sources_wellformed():
    names = [name for name, _, _ in SEED_SOURCES]
    assert len(names) == len(set(names)), "seed source names must be unique"
    for name, url, kind in SEED_SOURCES:
        assert url.startswith("https://"), (name, url)
        assert kind in ("m3u", "txt"), (name, kind)


def test_seed_source_urls_unique():
    """Two seed rows pointing at one URL waste a fetch slot and double-count
    the same streams, so duplicates must never be seeded."""
    urls = [url for _, url, _ in SEED_SOURCES]
    assert len(urls) == len(set(urls)), "seed source URLs must be unique"


def test_no_seed_pair_shares_content_stem():
    """Same repo path as both .m3u and .txt is a duplicate feed in disguise.

    guovin-gd-result-m3u and guovin-gd-result-txt parsed to byte-identical
    content (1618 entries, 1554 unique URLs, same names), so the txt seed owned
    zero URLs after first-wins dedup while still costing a fetch plus its share
    of the HTTP and ffprobe budget. Guard the pattern, not just exact URLs.
    """
    def stem(url):
        base = url.rsplit("/", 1)[-1]
        return (url.rsplit("/", 1)[0], base.rsplit(".", 1)[0].lower())

    stems = {}
    for name, url, _ in SEED_SOURCES:
        key = stem(url)
        if key in stems:
            raise AssertionError(
                f"{name} and {stems[key]} share content stem {key}; "
                "one of them is a duplicate feed")
        stems[key] = name


def test_seed_includes_cctv5_verified_sources():
    """These were probe-verified to uniquely own playable CCTV5 streams; the
    CCTV5 group is the reason they exist, so dropping one is a regression."""
    urls = "\n".join(url for _, url, _ in SEED_SOURCES)
    for frag in ("CCSH/IPTV",
                 "AS-D/iptv-api/master/output/result.m3u"):
        assert frag in urls, frag


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
