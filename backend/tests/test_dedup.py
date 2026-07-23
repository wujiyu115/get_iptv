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
