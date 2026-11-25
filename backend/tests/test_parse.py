from pipeline.parse import parse_m3u, parse_txt, extract_epg, parse

M3U = '''#EXTM3U url-tvg="http://epg.a/x.xml,http://epg.b/y.xml"
#EXTINF:-1 tvg-id="cctv1" tvg-name="CCTV1" tvg-logo="http://l/1.png" group-title="央视",CCTV1 综合
http://a/1.m3u8
#EXTINF:-1 group-title="测试",温馨提示
http://a/skip.m3u8
#EXTINF:-1 group-title="卫视",湖南卫视
http://a/2.m3u8
'''

# iptv-api 生成器头部的“更新时间”标记条目，频道名为时间戳
IPTV_API_M3U = '''#EXTM3U
#EXTINF:-1 tvg-name="CCTV1" group-title="🕘️更新时间",2025-05-26 06:16:51
http://a/1.m3u8
#EXTINF:-1 tvg-name="CCTV1" group-title="📺央视频道",CCTV-1
http://a/1.m3u8
'''

IPTV_API_TXT = '''🕘️更新时间,#genre#
2025-05-26 06:16:51,http://a/1.m3u8
央视频道,#genre#
CCTV-1,http://a/2.m3u8
'''

TXT = '''央视,#genre#
CCTV1,http://a/1.m3u8
CCTV2,http://a/2.m3u8
卫视,#genre#
湖南卫视,http://a/3.m3u8
'''


def test_parse_m3u_fields():
    es = parse_m3u(M3U, source="s1")
    assert len(es) == 2  # 温馨提示 被 SKIP_NAMES 丢弃
    e = es[0]
    assert e.name == "CCTV1 综合" and e.url == "http://a/1.m3u8"
    assert e.tvg_id == "cctv1" and e.logo == "http://l/1.png"
    assert e.group == "央视" and e.source == "s1"


def test_extract_epg():
    assert extract_epg(M3U) == ["http://epg.a/x.xml", "http://epg.b/y.xml"]


def test_parse_txt_genre():
    es = parse_txt(TXT, source="s2")
    assert len(es) == 3
    assert es[0].name == "CCTV1" and es[0].group == "央视"
    assert es[2].name == "湖南卫视" and es[2].group == "卫视"


def test_parse_dispatch():
    assert len(parse(M3U, "m3u")) == 2
    assert len(parse(TXT, "txt")) == 3


def test_parse_m3u_skips_update_time_marker():
    es = parse_m3u(IPTV_API_M3U, source="s3")
    assert len(es) == 1 and es[0].name == "CCTV-1"


def test_parse_txt_skips_update_time_marker():
    es = parse_txt(IPTV_API_TXT, source="s4")
    assert len(es) == 1 and es[0].name == "CCTV-1"


MULTICAST = '''#EXTM3U
#EXTINF:-1 group-title="央视",CCTV-1 综合
rtp://239.3.1.129:8008
#EXTINF:-1 group-title="央视",CCTV5 体育
udp://239.77.0.170:5146
'''

MULTICAST_TXT = '''央视,#genre#
CCTV-1 综合,rtp://239.3.1.129:8008
CCTV5 体育,udp://239.77.0.170:5146
'''


def test_parse_m3u_keeps_rtp_multicast():
    """rtp:// is IPTV multicast, as legitimate as udp://. Dropping it silently
    emptied whole multicast-only sources (every entry discarded)."""
    es = parse_m3u(MULTICAST, source="mc")
    assert [e.url for e in es] == ["rtp://239.3.1.129:8008",
                                   "udp://239.77.0.170:5146"]
    assert es[1].name == "CCTV5 体育"


def test_parse_txt_keeps_rtp_multicast():
    es = parse_txt(MULTICAST_TXT, source="mc")
    assert len(es) == 2 and es[0].url.startswith("rtp://")


UA_M3U = '''#EXTM3U
#EXTINF:-1 tvg-id="CCTV1" http-user-agent="AptvPlayer-UA" group-title="央视",CCTV1
http://101.35.240.114:88/live.php?id=CCTV1
#EXTINF:-1 user-agent="iPhone" group-title="央视",CCTV5
http://101.35.240.114:88/live.php?id=CCTV5
#EXTINF:-1 group-title="央视",CCTV6
http://a/6.m3u8
'''


def test_parse_m3u_reads_http_user_agent():
    """The migu live.php generator answers 404 to any UA but the one the feed
    names; dropping the attribute made ffprobe reject whole channel groups."""
    es = parse_m3u(UA_M3U, source="aptv")
    assert [e.ua for e in es] == ["AptvPlayer-UA", "iPhone", ""]


def test_parse_m3u_sanitizes_user_agent():
    """A UA reaches HTTP headers, m3u output and ffmpeg argv: strip quotes and
    control chars (header injection) and cap the length."""
    from pipeline.parse import _clean_ua

    assert _clean_ua('a"b\tc\rd') == "abcd"
    assert _clean_ua("  iPhone  ") == "iPhone"
    assert len(_clean_ua("u" * 500)) == 256
    # a quoted UA cannot smuggle an extra attribute into the EXTINF line either
    m = ('#EXTM3U\n#EXTINF:-1 http-user-agent="a\tb" group-title="g",X\n'
         'http://a/1\n')
    assert parse_m3u(m)[0].ua == "ab"
