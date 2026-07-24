import pytest

import pipeline.check_http as ch
from pipeline.check_http import classify_body
from pipeline.models import Entry, RunCancelled


def test_check_all_cancel_raises(monkeypatch):
    # stub the per-URL probe so no network happens; the cancel check inside the
    # as_completed loop must fire on the first completed future.
    monkeypatch.setattr(ch, "_check_one", lambda e, t: (e, "ok"))
    entries = [Entry(name=str(i), url="http://x") for i in range(30)]
    with pytest.raises(RunCancelled):
        ch.check_all(entries, should_cancel=lambda: True)


def test_check_all_no_cancel_completes(monkeypatch):
    monkeypatch.setattr(ch, "_check_one", lambda e, t: (e, "ok"))
    entries = [Entry(name=str(i), url="http://x") for i in range(5)]
    assert len(ch.check_all(entries, should_cancel=lambda: False)) == 5


def test_ok_m3u_body():
    assert classify_body(200, "application/x-mpegurl",
                          b"#EXTM3U\n#EXTINF:-1,A\nhttp://a/1\n") == "ok"


def test_ok_video_content_type():
    assert classify_body(200, "video/mp2t", b"\x00" * 500) == "ok"


def test_dead_non_200():
    assert classify_body(404, "text/html", b"not found") == "dead"


def test_ad_endlist_short_loop():
    body = b"#EXTM3U\n#EXT-X-ENDLIST\n"  # 极短 + ENDLIST = 占位
    assert classify_body(200, "application/x-mpegurl", body) == "ad"


def test_ad_keyword():
    assert classify_body(200, "text/plain", "这是广告占位".encode()) == "ad"
