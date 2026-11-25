from pipeline.models import Entry
from pipeline.dedup import dedup


def test_dedup_keeps_first_preserves_order():
    es = [
        Entry(name="A", url="http://X/1"),
        Entry(name="B", url="HTTP://x/1"),  # 大小写等价 -> 去掉
        Entry(name="C", url="http://X/2 "),  # 末尾空格
        Entry(name="D", url="http://x/2"),   # 与 C strip+lower 后等价 -> 去掉
    ]
    out = dedup(es)
    assert [e.name for e in out] == ["A", "C"]


def test_dedup_lifts_user_agent_from_duplicate():
    """Same URL listed by a UA-aware seed and a bare one: first wins, but the
    surviving entry must inherit the UA, otherwise the stream 404s from here on."""
    es = [
        Entry(name="CCTV1", url="http://h/live.php?id=CCTV1"),
        Entry(name="CCTV1", url="http://H/live.php?id=CCTV1", ua="AptvPlayer-UA"),
    ]
    out = dedup(es)
    assert len(out) == 1
    assert out[0].ua == "AptvPlayer-UA"
    assert out[0].name == "CCTV1"  # first-wins for the rest of the fields


def test_dedup_keeps_first_ua_when_both_present():
    es = [
        Entry(name="A", url="http://x/1", ua="UA1"),
        Entry(name="B", url="http://x/1", ua="UA2"),
    ]
    assert dedup(es)[0].ua == "UA1"
