from pipeline.check_http import classify_body


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
