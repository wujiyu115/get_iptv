from pipeline.block_hosts import apply, host_of, match_host, normalize_rules
from pipeline.models import Entry


def test_host_of_variants():
    assert host_of("http://example.com:8080/live.m3u8") == "example.com"
    assert host_of("https://User:Pass@Example.COM./x") == "example.com"
    assert host_of("rtmp://rtmp.example.com/live/1") == "rtmp.example.com"
    # 组播地址的 @ 前缀不是 userinfo，必须剥掉，否则规则对不上
    assert host_of("udp://@239.0.0.1:1234") == "239.0.0.1"
    assert host_of("http://[2001:db8::1]:8080/x") == "2001:db8::1"
    assert host_of("") == ""


def test_normalize_rules_dict_list_and_scalar():
    rules = normalize_rules({
        " CCTV5 ": {"183.250.156.180": "实测串播 CCTV6", "113.98.11.46": ""},
        "CCTV13": ["ali-m-l.cztv.com"],
        "CCTV9": "*.bad-host.com",
        "": {"x": "空频道名丢弃"},
        "CCTV1": [],
    })
    assert rules["cctv5"] == {"183.250.156.180": "实测串播 CCTV6", "113.98.11.46": ""}
    assert rules["cctv13"] == {"ali-m-l.cztv.com": ""}
    assert rules["cctv9"] == {"*.bad-host.com": ""}
    assert "" not in rules  # 空频道名
    assert "cctv1" not in rules  # 空列表不留空规则


def test_normalize_rules_garbage_is_ignored():
    assert normalize_rules(None) == {}
    assert normalize_rules("not-a-dict") == {}
    assert normalize_rules({"A": None}) == {}


def test_match_host_exact_and_wildcard():
    assert match_host({"h.com": "r"}, "h.com") == "r"
    assert match_host({"h.com": ""}, "h.com") == ""
    assert match_host({"h.com": ""}, "other.com") is None
    # 通配子域覆盖自身与所有子域，但不能误伤同后缀的别的域
    assert match_host({"*.h.com": ""}, "h.com") == ""
    assert match_host({"*.h.com": ""}, "a.b.h.com") == ""
    assert match_host({"*.h.com": ""}, "noth.com") is None


def test_apply_drops_only_matching_channel_and_host():
    rules = normalize_rules({"CCTV5": {"183.250.156.180": "串播 CCTV6"}})
    es = [
        Entry(name="CCTV5", url="http://183.250.156.180:8080/x.m3u8"),
        Entry(name="CCTV5", url="http://good.host/cctv5.m3u8"),
        Entry(name="CCTV6", url="http://183.250.156.180:8080/x.m3u8"),
    ]
    kept, dropped = apply(es, rules)
    assert [e.name for e in kept] == ["CCTV5", "CCTV6"]
    assert kept[0].url.endswith("good.host/cctv5.m3u8")
    assert [(e.name, r) for e, r in dropped] == [("CCTV5", "串播 CCTV6")]


def test_apply_channel_name_is_case_insensitive():
    es = [Entry(name="cctv5", url="http://bad.host/1.m3u8")]
    kept, dropped = apply(es, normalize_rules({"CCTV5": ["bad.host"]}))
    assert kept == []
    assert len(dropped) == 1


def test_apply_without_rules_is_noop():
    es = [Entry(name="A", url="http://a/1")]
    kept, dropped = apply(es, {})
    assert kept is es
    assert dropped == []
