import pytest

import pipeline.check_segment as cs
from pipeline.fetch import DEFAULT_UA
from pipeline.models import Entry, RunCancelled

MASTER = """#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360
low/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=4000000,RESOLUTION=1920x1080
hd/index.m3u8
"""

MEDIA = """#EXTM3U
#EXT-X-MAP:URI="init.mp4"
#EXTINF:4.0,
seg1.ts
#EXTINF:4.0,
seg2.ts
"""


class _Resp:
    def __init__(self, url, body, status=200):
        self.url = url
        self.status_code = status
        self._body = body

    def iter_bytes(self, n):
        yield self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Client:
    def __init__(self, pages, seen):
        self.pages = pages
        self.seen = seen

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def stream(self, method, url, headers=None):
        self.seen.append((url, (headers or {}).get("User-Agent")))
        if url not in self.pages:
            raise AssertionError(f"unexpected request: {url}")
        item = self.pages[url]
        if isinstance(item, Exception):
            raise item
        status, body = item
        return _Resp(url, body, status)


def _patch(monkeypatch, pages, seen):
    monkeypatch.setattr(cs.httpx, "Client", lambda *a, **k: _Client(pages, seen))


def test_pick_best_variant_highest_resolution():
    url, h = cs.pick_best_variant(MASTER, "http://h/master.m3u8")
    assert h == 1080
    assert url == "http://h/hd/index.m3u8"


def test_pick_best_variant_bandwidth_breaks_tie():
    text = ("#EXTM3U\n"
            "#EXT-X-STREAM-INF:BANDWIDTH=1000000,RESOLUTION=1280x720\na.m3u8\n"
            "#EXT-X-STREAM-INF:BANDWIDTH=3000000,RESOLUTION=1280x720\nb.m3u8\n")
    assert cs.pick_best_variant(text, "http://h/x/master.m3u8") == ("http://h/x/b.m3u8", 720)


def test_pick_best_variant_non_master():
    assert cs.pick_best_variant(MEDIA, "http://h/hd/index.m3u8") == ("", 0)
    assert cs.pick_best_variant("", "http://h/") == ("", 0)


def test_first_segment_skips_map_and_tags():
    assert cs.first_segment(MEDIA, "http://h/hd/index.m3u8") == "http://h/hd/seg1.ts"
    assert cs.first_segment("#EXTM3U\n#EXT-X-ENDLIST\n", "http://h/") == ""


def test_probe_entry_follows_master_and_measures_segment(monkeypatch):
    seen = []
    _patch(monkeypatch, {
        "http://h/live.php?id=CCTV1": (200, MASTER.encode()),
        "http://h/hd/index.m3u8": (200, MEDIA.encode()),
        "http://h/hd/seg1.ts": (200, b"x" * 200_000),
    }, seen)
    e = Entry(name="CCTV1", url="http://h/live.php?id=CCTV1", ua="AptvPlayer-UA")
    out = cs.probe_entry(e, timeout=3)
    assert out is e
    assert out.seg_kb == 200_000 // 1024
    assert out.resolution == 1080  # 顺手从 master 的 RESOLUTION 补上
    # 每一条请求都要带条目自己的 UA，否则 UA 门禁主机返回 404
    assert {ua for _, ua in seen} == {"AptvPlayer-UA"}
    # init 分片（#EXT-X-MAP）不能被当成首分片
    assert "http://h/hd/init.mp4" not in [u for u, _ in seen]


def test_probe_entry_caps_segment_bytes(monkeypatch):
    seen = []
    _patch(monkeypatch, {
        "http://h/index.m3u8": (200, MEDIA.encode()),
        "http://h/seg1.ts": (200, b"x" * (cs.MAX_SEG_BYTES * 3)),
    }, seen)
    e = cs.probe_entry(Entry(name="A", url="http://h/index.m3u8"), timeout=3)
    assert e.seg_kb == cs.MAX_SEG_BYTES // 1024  # 只统计到上限，不整段下载


def test_probe_entry_keeps_existing_resolution(monkeypatch):
    seen = []
    _patch(monkeypatch, {
        "http://h/index.m3u8": (200, MEDIA.encode()),
        "http://h/seg1.ts": (200, b"x" * 4096),
    }, seen)
    e = Entry(name="A", url="http://h/index.m3u8", resolution=2160)
    assert cs.probe_entry(e, timeout=3).resolution == 2160


def test_probe_entry_non_playlist_is_left_alone(monkeypatch):
    seen = []
    _patch(monkeypatch, {"http://h/x.ts": (200, b"\x47" * 4096)}, seen)
    e = cs.probe_entry(Entry(name="A", url="http://h/x.ts"), timeout=3)
    assert e.seg_kb == 0
    assert seen  # 探了一次就放弃，不算测量值


def test_probe_entry_skips_non_http(monkeypatch):
    seen = []
    _patch(monkeypatch, {}, seen)
    e = Entry(name="A", url="rtmp://h/live/1")
    assert cs.probe_entry(e, timeout=3).seg_kb == 0
    assert seen == []  # rtmp/udp 不探


def test_probe_entry_fail_open_on_error(monkeypatch):
    seen = []
    _patch(monkeypatch, {"http://h/x.m3u8": OSError("boom")}, seen)
    e = cs.probe_entry(Entry(name="A", url="http://h/x.m3u8"), timeout=3)
    assert e.seg_kb == 0  # 测不到 → 交给 check_http 判定，不在这里误杀


def test_probe_entry_hard_error_status_measures_zero(monkeypatch):
    seen = []
    _patch(monkeypatch, {"http://h/x.m3u8": (404, b"")}, seen)
    assert cs.probe_entry(Entry(name="A", url="http://h/x.m3u8"), 3).seg_kb == 0


def test_probe_entry_default_ua(monkeypatch):
    seen = []
    _patch(monkeypatch, {
        "http://h/index.m3u8": (200, MEDIA.encode()),
        "http://h/seg1.ts": (200, b"x" * 1024),
    }, seen)
    cs.probe_entry(Entry(name="A", url="http://h/index.m3u8"), timeout=3)
    assert {ua for _, ua in seen} == {DEFAULT_UA}


def test_check_all_disabled_is_noop(monkeypatch):
    seen = []
    _patch(monkeypatch, {}, seen)
    es = [Entry(name="A", url="http://h/x.m3u8")]
    logs = []
    assert cs.check_all(es, enabled=False, on_log=logs.append) is es
    assert seen == []
    assert es[0].seg_kb == 0
    assert any("disabled" in m for m in logs)


def test_check_all_fills_all_entries(monkeypatch):
    seen = []
    _patch(monkeypatch, {
        "http://h/index.m3u8": (200, MEDIA.encode()),
        "http://h/seg1.ts": (200, b"x" * 100_000),
    }, seen)
    es = [Entry(name="A", url="http://h/index.m3u8")]
    out = cs.check_all(es, enabled=True, workers=1)
    assert out == es and out[0].seg_kb == 97


def test_check_all_cancel_raises(monkeypatch):
    monkeypatch.setattr(cs, "probe_entry", lambda e, timeout=5: e)
    es = [Entry(name=str(i), url="http://h/x") for i in range(30)]
    with pytest.raises(RunCancelled):
        cs.check_all(es, enabled=True, workers=4, should_cancel=lambda: True)


def test_probe_entry_marks_segment_http_error_dead(monkeypatch):
    """playlist 正常但分片 404/403/5xx：这是确定性坏链，check_http 看不出来。"""
    seen = []
    _patch(monkeypatch, {
        "http://h/index.m3u8": (200, MEDIA.encode()),
        "http://h/seg1.ts": (404, b""),
    }, seen)
    e = cs.probe_entry(Entry(name="A", url="http://h/index.m3u8"), timeout=3)
    assert (e.seg_kb, e.seg_dead) == (0, True)


def test_probe_entry_timeout_is_not_dead(monkeypatch):
    """超时属于「不知道」，不能当死链，否则会误杀慢速但能看的源。"""
    seen = []
    _patch(monkeypatch, {
        "http://h/index.m3u8": (200, MEDIA.encode()),
        "http://h/seg1.ts": ReadTimeoutErr("slow"),
    }, seen)
    e = cs.probe_entry(Entry(name="A", url="http://h/index.m3u8"), timeout=3)
    assert (e.seg_kb, e.seg_dead) == (0, False)


def test_measure_segment_stops_after_window(monkeypatch):
    """只统计 SEG_WINDOW_S 内的吞吐，而不是整段下载：慢线拿多少算多少。"""

    class _R:
        status_code = 200

        def iter_bytes(self, n):
            for _ in range(10):
                yield b"x" * 8192

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _C:
        def stream(self, *a, **k):
            return _R()

    vals = [0.0, 0.0, 5.0]  # deadline=1.2，第二个 chunk 时已经超窗

    def fake_monotonic():
        return vals.pop(0) if vals else 5.0

    monkeypatch.setattr(cs.time, "monotonic", fake_monotonic)
    kb, dead = cs._measure_segment(_C(), "http://h/seg1.ts", "ua", 5)
    assert kb == 16  # 两个 8KB chunk 就停，不是 80KB
    assert dead is False


class ReadTimeoutErr(Exception):
    pass
