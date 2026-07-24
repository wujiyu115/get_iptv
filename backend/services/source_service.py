from db.database import get_conn

_SRC_FIELDS = ("name", "url", "type", "enabled", "use_proxy", "sort", "note")
_ALIAS_FIELDS = ("canonical", "pattern", "is_regex", "enabled")
_TMPL_FIELDS = ("canonical", "group_title", "logo", "sort", "enabled")


def _rows(sql, args=()):
    conn = get_conn()
    try:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def _insert(table, fields, d):
    cols = [f for f in fields if f in d]
    conn = get_conn()
    try:
        cur = conn.execute(
            f"INSERT INTO {table}({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            [d[c] for c in cols])
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _update(table, fields, _id, d):
    cols = [f for f in fields if f in d]
    if not cols:
        return
    conn = get_conn()
    try:
        conn.execute(f"UPDATE {table} SET {','.join(c + '=?' for c in cols)} WHERE id=?",
                    [d[c] for c in cols] + [_id])
        conn.commit()
    finally:
        conn.close()


def _delete(table, _id):
    conn = get_conn()
    try:
        conn.execute(f"DELETE FROM {table} WHERE id=?", (_id,))
        conn.commit()
    finally:
        conn.close()


def list_sources(): return _rows("SELECT * FROM sources ORDER BY sort, id")
def create_source(d): return _insert("sources", _SRC_FIELDS, d)
def update_source(i, d):
    # Re-enabling a source clears its accumulated fail_count so one more
    # failure won't immediately re-trip the auto-disable threshold.
    if int(d.get("enabled", 0)) == 1:
        d = {**d, "fail_count": 0}
    _update("sources", (*_SRC_FIELDS, "fail_count"), i, d)
def delete_source(i): _delete("sources", i)

def list_aliases(): return _rows("SELECT * FROM aliases ORDER BY id")
def create_alias(d): return _insert("aliases", _ALIAS_FIELDS, d)
def update_alias(i, d): _update("aliases", _ALIAS_FIELDS, i, d)
def delete_alias(i): _delete("aliases", i)

def list_templates(): return _rows("SELECT * FROM templates ORDER BY sort, id")
def create_template(d): return _insert("templates", _TMPL_FIELDS, d)
def update_template(i, d): _update("templates", _TMPL_FIELDS, i, d)
def delete_template(i): _delete("templates", i)
