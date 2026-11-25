from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.proxy as proxymod
from pipeline.fetch import DEFAULT_UA
from routes.proxy import _rewrite_m3u8


def test_rewrite_segments_and_uri_attrs():
    m3u8 = (
        "#EXTM3U\n"
        "#EXT-X-KEY:METHOD=AES-128,URI=\"key.bin\"\n"
        "#EXTINF:6,\n"
        "seg1.ts\n"
        "#EXTINF:6,\n"
        "http://cdn/abs/seg2.ts\n"
    )
    out = _rewrite_m3u8(m3u8, "http://host/live/index.m3u8")
    # relative + absolute segment lines both routed through the proxy
    assert "/api/proxy?url=http%3A%2F%2Fhost%2Flive%2Fseg1.ts" in out
    assert "/api/proxy?url=http%3A%2F%2Fcdn%2Fabs%2Fseg2.ts" in out
    # EXT-X-KEY URI rewritten, tag structure preserved
    assert 'URI="/api/proxy?url=http%3A%2F%2Fhost%2Flive%2Fkey.bin"' in out
    assert out.startswith("#EXTM3U")


class _FakeResp:
    def __init__(self, url, body, ct, status=200, extra=None):
        self.url = url
        self._body = body
        self.headers = {"content-type": ct, **(extra or {})}
        self.status_code = status

    async def aread(self):
        return self._body

    async def aclose(self):
        pass

    async def aiter_bytes(self, n):
        yield self._body


def _fake_client(body, ct, status=200, extra=None):
    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        def build_request(self, method, url, headers=None):
            return SimpleNamespace(url=url)

        async def send(self, req, stream=True):
            return _FakeResp(req.url, body, ct, status, extra)

        async def aclose(self):
            pass

    return _FakeClient


def _client():
    app = FastAPI()
    app.include_router(proxymod.router)
    return TestClient(app)


def test_m3u8_response_is_not_cached(monkeypatch):
    monkeypatch.setattr(proxymod.httpx, "AsyncClient",
                        _fake_client(b"#EXTM3U\n#EXTINF:6,\nseg1.ts\n",
                                     "application/vnd.apple.mpegurl"))
    r = _client().get("/api/proxy", params={"url": "http://host/live/index.m3u8"})
    assert r.status_code == 200
    assert "no-store" in r.headers.get("cache-control", "")
    assert "/api/proxy?url=" in r.text  # segment rewritten


def test_segment_status_passthrough(monkeypatch):
    # a purged live segment must surface as 404, not be masked
    monkeypatch.setattr(proxymod.httpx, "AsyncClient",
                        _fake_client(b"", "video/mp2t", status=404))
    r = _client().get("/api/proxy", params={"url": "http://host/live/235400.ts"})
    assert r.status_code == 404


class _FakeStdout:
    def __init__(self, chunks):
        self._c = list(chunks)

    async def read(self, n):
        return self._c.pop(0) if self._c else b""


class _FakeProc:
    def __init__(self):
        self.stdout = _FakeStdout([b"\x47" + b"\x00" * 187, b""])
        self.returncode = 0

    def kill(self):
        pass

    async def wait(self):
        return 0


def test_restream_streams_ffmpeg_output(monkeypatch):
    monkeypatch.setattr(proxymod.shutil, "which", lambda n: "/usr/bin/ffmpeg")

    async def _fake_exec(*a, **k):
        return _FakeProc()

    monkeypatch.setattr(proxymod.asyncio, "create_subprocess_exec", _fake_exec)
    r = _client().get("/api/restream", params={"url": "http://host/live/x.m3u8"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("video/mp2t")
    assert r.content[:1] == b"\x47"  # TS sync byte


def test_restream_rejects_non_http(monkeypatch):
    monkeypatch.setattr(proxymod.shutil, "which", lambda n: "/usr/bin/ffmpeg")
    assert _client().get("/api/restream", params={"url": "ftp://h/x"}).status_code == 400


def test_restream_501_without_ffmpeg(monkeypatch):
    monkeypatch.setattr(proxymod.shutil, "which", lambda n: None)
    assert _client().get("/api/restream",
                         params={"url": "http://h/x.m3u8"}).status_code == 501


def test_restream_cmd_transcodes_to_ts():
    cmd = proxymod._ffmpeg_restream_cmd("http://h/x.m3u8")
    assert cmd[0] == "ffmpeg" and cmd[-1] == "-"
    # re-encode (not copy) so undecodable source frames are rebuilt cleanly
    assert "libx264" in cmd and "aac" in cmd and "mpegts" in cmd
    assert "copy" not in cmd
    assert cmd[cmd.index("-i") + 1] == "http://h/x.m3u8"


def test_partial_content_forwards_range_headers(monkeypatch):
    # 206 must carry Content-Range through, else range players abort
    monkeypatch.setattr(proxymod.httpx, "AsyncClient",
                        _fake_client(b"\x47" * 188, "video/mp2t", status=206,
                                     extra={"content-range": "bytes 0-187/100000",
                                            "content-length": "188"}))
    r = _client().get("/api/proxy", params={"url": "http://1.2.3.4:85/live_1.ts?key=x"})
    assert r.status_code == 206
    assert r.headers.get("content-range") == "bytes 0-187/100000"
    assert r.headers.get("accept-ranges") == "bytes"


# --- per-entry UA passthrough -------------------------------------------------
# A UA-gated upstream (migu live.php) answers 404 to the proxy's default UA, so
# the entry's own UA has to reach both the request and every child segment.

def _capturing_client(sink, body, ct):
    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        def build_request(self, method, url, headers=None):
            sink["headers"] = headers or {}
            return SimpleNamespace(url=url)

        async def send(self, req, stream=True):
            return _FakeResp(req.url, body, ct)

        async def aclose(self):
            pass

    return _FakeClient


def test_proxy_forwards_entry_ua_and_propagates_to_segments(monkeypatch):
    sink = {}
    body = b"#EXTM3U\n#EXTINF:6,\nseg1.ts\n"
    monkeypatch.setattr(proxymod.httpx, "AsyncClient",
                        _capturing_client(sink, body, "application/vnd.apple.mpegurl"))
    r = _client().get("/api/proxy",
                      params={"url": "http://101.35.240.114:88/live.php?id=CCTV1",
                              "ua": "AptvPlayer-UA"})
    assert r.status_code == 200
    assert sink["headers"]["User-Agent"] == "AptvPlayer-UA"
    # child requests must keep the UA, else every segment 404s upstream
    assert "ua=AptvPlayer-UA" in r.text


def test_proxy_uses_default_ua_without_param(monkeypatch):
    sink = {}
    monkeypatch.setattr(proxymod.httpx, "AsyncClient",
                        _capturing_client(sink, b"\x47" * 188, "video/mp2t"))
    _client().get("/api/proxy", params={"url": "http://h/live/1.ts"})
    assert sink["headers"]["User-Agent"] == DEFAULT_UA


def test_rewrite_m3u8_carries_ua():
    out = _rewrite_m3u8("#EXTM3U\n#EXTINF:6,\nseg1.ts\n",
                        "http://host/live/index.m3u8", "iPhone")
    assert "&ua=iPhone" in out


@pytest.mark.parametrize("bad", [
    "a\r\nX-Injected: 1",   # header injection
    "a\nb",
    "-oops",                # ffmpeg would parse it as an option
    "u" * 300,              # absurdly long
    "",
])
def test_safe_ua_rejects_unusable_values(bad):
    assert proxymod.safe_ua(bad) == ""


def test_safe_ua_keeps_normal_values():
    assert proxymod.safe_ua("  AptvPlayer-UA  ") == "AptvPlayer-UA"
    assert proxymod.safe_ua("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)") == \
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)"


def test_restream_cmd_uses_entry_ua():
    cmd = proxymod._ffmpeg_restream_cmd("http://h/x.m3u8", "AptvPlayer-UA")
    assert cmd[cmd.index("-user_agent") + 1] == "AptvPlayer-UA"
    assert proxymod._ffmpeg_restream_cmd("http://h/x.m3u8")[
        proxymod._ffmpeg_restream_cmd("http://h/x.m3u8").index("-user_agent") + 1
    ] == DEFAULT_UA


def test_restream_route_passes_ua(monkeypatch):
    seen = {}

    async def _fake_exec(*a, **k):
        seen["argv"] = list(a)
        return _FakeProc()

    monkeypatch.setattr(proxymod.shutil, "which", lambda n: "/usr/bin/ffmpeg")
    monkeypatch.setattr(proxymod.asyncio, "create_subprocess_exec", _fake_exec)
    _client().get("/api/restream",
                  params={"url": "http://h/x.m3u8", "ua": "AptvPlayer-UA"})
    assert seen["argv"][seen["argv"].index("-user_agent") + 1] == "AptvPlayer-UA"
