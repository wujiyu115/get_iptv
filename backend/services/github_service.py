import json
import os
import re
import time
import urllib.parse
import urllib.request

# https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path...>
_RAW = re.compile(r"^https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)$")
_TTL = 6 * 3600  # commit dates change slowly; cache to stay under the API rate limit
_cache: dict[str, tuple[str | None, float]] = {}


def _api_last_commit(owner: str, repo: str, branch: str, path: str) -> str | None:
    q = urllib.parse.quote(path)
    url = (f"https://api.github.com/repos/{owner}/{repo}/commits"
           f"?path={q}&sha={branch}&per_page=1")
    headers = {"User-Agent": "iptv-agg", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.load(r)
    if data:
        return data[0]["commit"]["committer"]["date"]
    return None


def last_updated(url: str, now: float | None = None) -> str | None:
    """Last commit date (ISO) for a raw.githubusercontent URL, else None.

    Cached for _TTL seconds; on API error the last cached value is kept.
    """
    m = _RAW.match(url or "")
    if not m:
        return None
    now = time.time() if now is None else now
    hit = _cache.get(url)
    if hit and now - hit[1] < _TTL:
        return hit[0]
    try:
        date = _api_last_commit(*m.groups())
    except Exception:  # noqa: BLE001 - network/rate-limit: fall back to stale
        date = hit[0] if hit else None
    _cache[url] = (date, now)
    return date
