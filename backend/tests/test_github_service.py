import io
import json

import services.github_service as gh


class _Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def _fake_urlopen(payload):
    def _open(req, timeout=None):
        return _Resp(json.dumps(payload).encode())
    return _open


def setup_function():
    gh._cache.clear()


def test_non_github_url_returns_none():
    assert gh.last_updated("https://example.com/x.m3u") is None
    assert gh.last_updated("") is None


def test_raw_github_parsed_and_cached(monkeypatch):
    calls = {"n": 0}

    def _open(req, timeout=None):
        calls["n"] += 1
        return _Resp(json.dumps(
            [{"commit": {"committer": {"date": "2026-07-24T10:00:00Z"}}}]).encode())

    monkeypatch.setattr(gh.urllib.request, "urlopen", _open)
    url = "https://raw.githubusercontent.com/o/r/main/a/b.m3u"
    assert gh.last_updated(url, now=1000) == "2026-07-24T10:00:00Z"
    # within TTL -> served from cache, no second API call
    assert gh.last_updated(url, now=1000 + 60) == "2026-07-24T10:00:00Z"
    assert calls["n"] == 1
    # past TTL -> refetch
    gh.last_updated(url, now=1000 + gh._TTL + 1)
    assert calls["n"] == 2


def test_api_error_keeps_stale_value(monkeypatch):
    url = "https://raw.githubusercontent.com/o/r/main/a/b.m3u"
    monkeypatch.setattr(gh.urllib.request, "urlopen",
                        _fake_urlopen([{"commit": {"committer": {"date": "2026-01-01T00:00:00Z"}}}]))
    assert gh.last_updated(url, now=1) == "2026-01-01T00:00:00Z"

    def _boom(req, timeout=None):
        raise OSError("network down")

    monkeypatch.setattr(gh.urllib.request, "urlopen", _boom)
    # stale value retained rather than dropping to None
    assert gh.last_updated(url, now=1 + gh._TTL + 1) == "2026-01-01T00:00:00Z"


def test_empty_commit_list_returns_none(monkeypatch):
    monkeypatch.setattr(gh.urllib.request, "urlopen", _fake_urlopen([]))
    assert gh.last_updated(
        "https://raw.githubusercontent.com/o/r/main/x.m3u", now=5) is None
