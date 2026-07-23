# (name, url, type)
SEED_SOURCES = [
    ("iptv-org-cn", "https://iptv-org.github.io/iptv/countries/cn.m3u", "m3u"),
    ("guovin-gd-result-m3u",
     "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u", "m3u"),
    ("guovin-gd-result-txt",
     "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.txt", "txt"),
    ("yang-gather", "https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u", "m3u"),
    ("yang-migu", "https://raw.githubusercontent.com/YanG-1989/m3u/main/Migu.m3u", "m3u"),
]

# (canonical, pattern, is_regex)
SEED_ALIASES = [
    ("CCTV1", r"^CCTV[-\s]?1(\s|综合|$)", 1),
    ("CCTV2", r"^CCTV[-\s]?2(\s|财经|$)", 1),
    ("CCTV5", r"^CCTV[-\s]?5(\s|体育|$)", 1),
    ("CCTV5+", r"^CCTV[-\s]?5\+(\s|体育赛事|$)", 1),
    ("CCTV13", r"^CCTV[-\s]?13(\s|新闻|$)", 1),
    ("湖南卫视", r"湖南卫视", 0),
    ("浙江卫视", r"浙江卫视", 0),
    ("东方卫视", r"东方卫视", 0),
    ("江苏卫视", r"江苏卫视", 0),
    ("北京卫视", r"北京卫视", 0),
]
