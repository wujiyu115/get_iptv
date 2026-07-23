import re

from pipeline.models import Entry


def apply_aliases(entries: list[Entry], aliases: list[dict]) -> list[Entry]:
    for e in entries:
        for a in aliases:
            pat, canon = a["pattern"], a["canonical"]
            hit = (re.search(pat, e.name) if a.get("is_regex") else pat in e.name)
            if hit:
                e.name = canon
                break
    return entries


def apply_templates(entries: list[Entry], templates: list[dict],
                    keep_unmatched: bool = True) -> list[Entry]:
    if not templates:
        return entries
    by_canon = {t["canonical"]: t for t in templates}
    out: list[Entry] = []
    for e in entries:
        t = by_canon.get(e.name)
        if t:
            if t.get("group_title"):
                e.group = t["group_title"]
            if t.get("logo") and not e.logo:
                e.logo = t["logo"]
            setattr(e, "_tmpl_sort", t.get("sort", 0))
            out.append(e)
        elif keep_unmatched:
            setattr(e, "_tmpl_sort", 10_000)
            out.append(e)
    return out
