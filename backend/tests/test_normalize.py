from pipeline.models import Entry
from pipeline.normalize import apply_aliases, apply_templates


def test_alias_regex_and_substring():
    es = [Entry(name="CCTV-1 综合", url="u1"), Entry(name="湖南卫视HD", url="u2")]
    aliases = [
        {"canonical": "CCTV1", "pattern": r"^CCTV[-\s]?1(\s|综合|$)", "is_regex": True},
        {"canonical": "湖南卫视", "pattern": "湖南卫视", "is_regex": False},
    ]
    out = apply_aliases(es, aliases)
    assert out[0].name == "CCTV1"
    assert out[1].name == "湖南卫视"


def test_template_sets_group_and_keeps_unmatched():
    es = [Entry(name="CCTV1", url="u1"), Entry(name="未知台", url="u2")]
    tmpls = [{"canonical": "CCTV1", "group_title": "央视", "logo": "L", "sort": 1}]
    out = apply_templates(es, tmpls, keep_unmatched=True)
    assert out[0].group == "央视" and out[0].logo == "L"
    assert len(out) == 2  # 未匹配保留


def test_template_drop_unmatched():
    es = [Entry(name="CCTV1", url="u1"), Entry(name="未知台", url="u2")]
    tmpls = [{"canonical": "CCTV1", "group_title": "央视", "logo": "", "sort": 1}]
    out = apply_templates(es, tmpls, keep_unmatched=False)
    assert [e.name for e in out] == ["CCTV1"]


def test_empty_templates_keep_all():
    es = [Entry(name="X", url="u")]
    assert len(apply_templates(es, [], keep_unmatched=True)) == 1
