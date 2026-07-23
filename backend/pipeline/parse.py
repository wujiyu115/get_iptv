import re

from pipeline.models import Entry

SKIP_NAMES = ["温馨提示", "免费订阅", "维护", "使用说明", "Github", "更新时间"]
_URL_PREFIX = ("http://", "https://", "rtmp://", "rtsp://", "udp://")


def _skip(name: str) -> bool:
    return any(s in name for s in SKIP_NAMES)


def extract_epg(text: str) -> list[str]:
    urls: list[str] = []
    for line in text.splitlines():
        if not line.startswith("#EXTM3U"):
            continue
        for m in re.finditer(r'(?:url-tvg|x-tvg-url)="([^"]*)"', line):
            for u in re.split(r"[;,]", m.group(1)):
                u = u.strip()
                if u:
                    urls.append(u)
    return urls


def parse_m3u(text: str, source: str = "") -> list[Entry]:
    entries: list[Entry] = []
    cur: dict | None = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#EXTINF"):
            name_m = re.search(r",(.+)$", line)
            cur = {
                "name": (name_m.group(1).strip() if name_m else ""),
                "logo": _attr(line, "tvg-logo"),
                "group": _attr(line, "group-title"),
                "tvg_id": _attr(line, "tvg-id"),
                "tvg_name": _attr(line, "tvg-name"),
            }
        elif line.startswith(_URL_PREFIX) and cur is not None:
            if cur["name"] and not _skip(cur["name"]):
                entries.append(Entry(url=line, source=source, **cur))
            cur = None
    return entries


def parse_txt(text: str, source: str = "") -> list[Entry]:
    entries: list[Entry] = []
    group = ""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.endswith("#genre#"):
            group = line.split(",")[0].strip()
            continue
        if "," in line:
            name, url = line.split(",", 1)
            name, url = name.strip(), url.strip()
            if name and url.startswith(_URL_PREFIX) and not _skip(name):
                entries.append(Entry(name=name, url=url, group=group, source=source))
    return entries


def parse(text: str, kind: str, source: str = "") -> list[Entry]:
    return parse_txt(text, source) if kind == "txt" else parse_m3u(text, source)


def _attr(line: str, key: str) -> str:
    m = re.search(key + r'="([^"]*)"', line)
    return m.group(1) if m else ""
