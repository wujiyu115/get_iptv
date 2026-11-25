from pipeline.models import Entry


def dedup(entries: list[Entry]) -> list[Entry]:
    """First-wins on URL, but keep the most informative User-Agent.

    The same stream is often listed by several seeds; only some of them spell
    out the required UA. Dropping the duplicates outright would throw that away
    and the surviving entry would then 404 in ffprobe and in the player, so a
    bare entry is upgraded in place when a duplicate carries a UA.
    """
    seen: dict[str, Entry] = {}
    out: list[Entry] = []
    for e in entries:
        key = e.url.strip().lower()
        hit = seen.get(key)
        if hit is None:
            seen[key] = e
            out.append(e)
        elif e.ua and not hit.ua:
            hit.ua = e.ua
    return out
