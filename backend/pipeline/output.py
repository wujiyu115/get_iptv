import os
from collections import OrderedDict

from pipeline.models import Entry


def _header(epg_urls) -> str:
    if epg_urls:
        return '#EXTM3U url-tvg="' + ",".join(epg_urls) + '"'
    return "#EXTM3U"


def _extinf(e: Entry, open_url_info: bool) -> str:
    name = e.name
    if open_url_info:
        info = []
        if e.resolution:
            info.append(f"{e.resolution}p")
        if e.source:
            info.append(e.source)
        if info:
            name = f"{name} ${'|'.join(info)}"
    group = e.group or "其他"
    return (f'#EXTINF:-1 tvg-id="{e.tvg_id}" tvg-name="{e.tvg_name or e.name}" '
            f'tvg-logo="{e.logo}" group-title="{group}",{name}')


def _compact(entries: list[Entry]) -> list[Entry]:
    seen: "OrderedDict[str, Entry]" = OrderedDict()
    for e in entries:
        if e.name not in seen:
            seen[e.name] = e
    return list(seen.values())


def build_full_m3u(entries, *, epg_urls=None, open_url_info=False) -> str:
    lines = [_header(epg_urls)]
    for e in entries:
        lines.append(_extinf(e, open_url_info))
        lines.append(e.url)
    return "\n".join(lines) + "\n"


def build_compact_m3u(entries, *, epg_urls=None, open_url_info=False) -> str:
    lines = [_header(epg_urls)]
    for e in _compact(entries):
        lines.append(_extinf(e, open_url_info))
        lines.append(e.url)
    return "\n".join(lines) + "\n"


def build_txt(entries) -> str:
    lines: list[str] = []
    cur_group = None
    for e in _compact(entries):
        g = e.group or "其他"
        if g != cur_group:
            if lines:
                lines.append("")
            lines.append(f"{g},#genre#")
            cur_group = g
        lines.append(f"{e.name},{e.url}")
    return "\n".join(lines) + "\n"


def write_all(entries, out_dir, *, epg_urls=None, open_epg=True,
              open_url_info=False) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    epg = epg_urls if open_epg else None
    files = {
        "full.m3u": build_full_m3u(entries, epg_urls=epg, open_url_info=open_url_info),
        "compact.m3u": build_compact_m3u(entries, epg_urls=epg, open_url_info=open_url_info),
        "iptv.txt": build_txt(entries),
    }
    # atomic swap: write .tmp then os.replace, so the previous result stays
    # served intact until the new one is fully written on success.
    paths = {}
    for name, content in files.items():
        p = os.path.join(out_dir, name)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, p)
        paths[name] = p
    return paths
