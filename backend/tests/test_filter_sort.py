from pipeline.models import Entry
from pipeline.filter_sort import apply, parse_resolution


def test_parse_resolution():
    assert parse_resolution("1920x1080") == 1080
    assert parse_resolution("1280x720") == 720
    assert parse_resolution("bad") == 0


def test_min_resolution_filter():
    es = [Entry(name="A", url="u1", resolution=1080),
          Entry(name="A", url="u2", resolution=480)]
    out = apply(es, min_resolution="1280x720")
    assert [e.url for e in out] == ["u1"]


def test_sort_and_urls_limit_per_channel():
    es = [
        Entry(name="A", url="lo", resolution=480, speed=2.0),
        Entry(name="A", url="hi", resolution=1080, speed=1.0),
        Entry(name="A", url="mid", resolution=720, speed=9.0),
    ]
    out = apply(es, sort_by="resolution,speed", urls_limit=2)
    a = [e.url for e in out if e.name == "A"]
    assert a == ["hi", "mid"]  # 分辨率优先，截断到 2


def test_speed_zero_not_dropped_when_min_speed_set():
    es = [Entry(name="A", url="u", resolution=1080, speed=0.0)]
    out = apply(es, min_speed=0.5)
    assert len(out) == 1  # speed==0 视为未测速，保留
