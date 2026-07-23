import re
from collections import OrderedDict

from pipeline.models import Entry


def parse_resolution(s: str) -> int:
    m = re.match(r"\s*\d+\s*[xX]\s*(\d+)", s or "")
    return int(m.group(1)) if m else 0


def _sort_key(sort_by: str):
    fields = [f.strip() for f in sort_by.split(",") if f.strip()]

    def key(e: Entry):
        parts = []
        for f in fields:
            if f == "resolution":
                parts.append(-e.resolution)
            elif f == "speed":
                parts.append(-e.speed)
            elif f == "delay":
                parts.append(e.delay if e.delay > 0 else float("inf"))
        return tuple(parts)

    return key


def apply(entries: list[Entry], *, min_resolution: str = "", min_speed: float = 0.0,
          sort_by: str = "resolution,speed", urls_limit: int = 0) -> list[Entry]:
    min_h = parse_resolution(min_resolution)
    kept = []
    for e in entries:
        if min_h and e.resolution and e.resolution < min_h:
            continue
        if min_speed and e.speed and e.speed < min_speed:
            continue
        kept.append(e)

    kept.sort(key=_sort_key(sort_by))

    if urls_limit and urls_limit > 0:
        counts: dict[str, int] = {}
        limited = []
        for e in kept:
            c = counts.get(e.name, 0)
            if c < urls_limit:
                counts[e.name] = c + 1
                limited.append(e)
        kept = limited

    # regroup so same channel's urls stay adjacent, groups in first-seen order
    buckets: "OrderedDict[str, list[Entry]]" = OrderedDict()
    for e in kept:
        buckets.setdefault(e.name, []).append(e)
    out: list[Entry] = []
    for v in buckets.values():
        out.extend(v)
    return out
