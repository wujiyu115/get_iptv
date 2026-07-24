from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.proxy as proxymod
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
