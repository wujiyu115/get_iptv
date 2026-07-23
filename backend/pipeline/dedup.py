from pipeline.models import Entry


def dedup(entries: list[Entry]) -> list[Entry]:
    seen: set[str] = set()
    out: list[Entry] = []
    for e in entries:
        key = e.url.strip().lower()
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out
