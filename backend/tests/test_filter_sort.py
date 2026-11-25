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


def test_min_seg_kb_filters_slow_keeps_unmeasured():
    es = [Entry(name="A", url="slow", resolution=1080, seg_kb=40),
          Entry(name="A", url="ok", resolution=1080, seg_kb=200),
          Entry(name="A", url="unmeasured", resolution=1080, seg_kb=0)]
    out = apply(es, min_seg_kb=80)
    assert sorted(e.url for e in out) == ["ok", "unmeasured"]  # 未测(0)不放杀


def test_min_seg_kb_zero_disables():
    es = [Entry(name="A", url="slow", resolution=1080, seg_kb=1)]
    assert len(apply(es, min_seg_kb=0)) == 1


def test_min_seg_kb_drops_known_dead_segment():
    """playlist 正常但分片明确报错 = 确定坏链；只有开了 min_seg_kb 才动它。"""
    es = [Entry(name="A", url="dead", resolution=1080, seg_dead=True),
          Entry(name="A", url="ok", resolution=1080, seg_kb=200)]
    assert [e.url for e in apply(es, min_seg_kb=80)] == ["ok"]
    assert len(apply(es, min_seg_kb=0)) == 2  # 未开启时不动
