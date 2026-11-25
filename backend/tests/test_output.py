from pipeline.models import Entry
from pipeline.output import build_full_m3u, build_compact_m3u, build_txt, write_all


def _sample():
    return [
        Entry(name="CCTV1", url="u1", group="央视", logo="L1", resolution=1080),
        Entry(name="CCTV1", url="u2", group="央视", logo="L1", resolution=720),
        Entry(name="湖南卫视", url="u3", group="卫视", resolution=1080),
    ]


def test_full_m3u_has_all_urls_and_epg():
    m = build_full_m3u(_sample(), epg_urls=["http://epg/x.xml"])
    assert m.startswith("#EXTM3U")
    assert 'url-tvg="http://epg/x.xml"' in m
    assert m.count("#EXTINF") == 3
    assert "u1" in m and "u2" in m and "u3" in m


def test_compact_one_per_channel():
    m = build_compact_m3u(_sample())
    assert m.count("#EXTINF") == 2  # CCTV1 只留一条 + 湖南卫视
    assert "u1" in m and "u2" not in m


def test_txt_genre_format():
    t = build_txt(_sample())
    assert "央视,#genre#" in t
    assert "CCTV1,u1" in t
    assert "湖南卫视,u3" in t


def test_write_all(tmp_path):
    files = write_all(_sample(), str(tmp_path), epg_urls=None)
    assert (tmp_path / "full.m3u").exists()
    assert (tmp_path / "compact.m3u").exists()
    assert (tmp_path / "iptv.txt").exists()
    assert set(files) == {"full.m3u", "compact.m3u", "iptv.txt"}


def test_full_m3u_carries_user_agent_and_round_trips():
    """Downstream players (APTV/TiviMate) honour http-user-agent, so a direct
    consumer of full.m3u plays UA-gated URLs; parsing our own output must give
    the UA back."""
    from pipeline.parse import parse_m3u

    entries = [Entry(name="CCTV1", url="http://h/live.php?id=CCTV1",
                     group="央视", ua="AptvPlayer-UA"),
               Entry(name="CCTV2", url="http://h/2", group="央视")]
    m = build_full_m3u(entries)
    assert 'http-user-agent="AptvPlayer-UA"' in m
    assert m.count("http-user-agent=") == 1  # only when set
    back = parse_m3u(m)
    assert [e.ua for e in back] == ["AptvPlayer-UA", ""]
    assert [e.url for e in back] == [e.url for e in entries]
