import os
import sqlite3

from config.config_loader import config
from db.seed import SEED_SOURCES, SEED_ALIASES

_here = os.path.dirname(os.path.abspath(__file__))
_schema = os.path.join(_here, "schema.sql")


def db_path() -> str:
    p = os.environ.get("DB_PATH") or config.get("db.path", "./data/iptv.db")
    p = os.path.abspath(p)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive column migrations for DBs created by an older schema.

    schema.sql only uses CREATE TABLE IF NOT EXISTS, so it never touches an
    existing table; new columns have to be added explicitly or every query that
    names them fails on an upgraded install.
    """
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(channels)")}
    if "ua" not in cols:
        conn.execute("ALTER TABLE channels ADD COLUMN ua TEXT DEFAULT ''")


def init_db(conn: sqlite3.Connection = None) -> None:
    own = conn is None
    conn = conn or get_conn()
    with open(_schema, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    _migrate(conn)
    if conn.execute("SELECT COUNT(*) c FROM sources").fetchone()["c"] == 0:
        conn.executemany(
            "INSERT INTO sources(name,url,type) VALUES (?,?,?)", SEED_SOURCES)
        conn.executemany(
            "INSERT INTO aliases(canonical,pattern,is_regex) VALUES (?,?,?)",
            SEED_ALIASES)
        conn.commit()
    if own:
        conn.commit()
        conn.close()
