import pipeline.fetch as fetch


class _Resp:
    def __init__(self, text): self.text = text
    def raise_for_status(self): pass


class _Client:
    def __init__(self, *a, **k): pass
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def get(self, url, headers=None):
        if "bad" in url:
            raise RuntimeError("boom")
        return _Resp("#EXTM3U\n#EXTINF:-1,A\nhttp://a/1\n")


def test_fetch_one_ok(monkeypatch):
    monkeypatch.setattr(fetch.httpx, "Client", _Client)
    src = {"name": "s", "url": "http://ok", "type": "m3u", "use_proxy": 0}
    s, text = fetch.fetch_one(src, retries=0)
    assert text and "#EXTM3U" in text


def test_fetch_one_fail_returns_none(monkeypatch):
    monkeypatch.setattr(fetch.httpx, "Client", _Client)
    src = {"name": "s", "url": "http://bad", "type": "m3u", "use_proxy": 0}
    s, text = fetch.fetch_one(src, retries=1)
    assert text is None


def test_fetch_all_skips_failures(monkeypatch):
    monkeypatch.setattr(fetch.httpx, "Client", _Client)
    srcs = [{"name": "ok", "url": "http://ok", "type": "m3u", "use_proxy": 0},
            {"name": "bad", "url": "http://bad", "type": "m3u", "use_proxy": 0}]
    out = fetch.fetch_all(srcs, retries=0)
    assert [s["name"] for s, _ in out] == ["ok"]
