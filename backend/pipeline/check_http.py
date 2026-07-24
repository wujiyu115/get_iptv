from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from pipeline.fetch import DEFAULT_UA
from pipeline.models import Entry

AD_KEYWORDS = ["广告", "占位", "advertisement", "sponsor"]
_HTTP = ("http://", "https://")


def classify_body(code: int, content_type: str, body: bytes) -> str:
    bs = body.decode("utf-8", errors="replace").lower()
    ct = (content_type or "").lower()
    if any(k.lower() in bs for k in AD_KEYWORDS):
        return "ad"
    if "#ext-x-endlist" in bs and len(body) < 300:
        return "ad"
    if code == 200 and ("#extm3u" in bs or "#extinf" in bs
                        or "video" in ct or len(body) > 200):
        return "ok"
    return "dead"


def _check_one(e: Entry, timeout: int):
    if not e.url.startswith(_HTTP):
        return e, "ok"  # rtmp/rtsp/udp bypass HTTP check
    try:
        with httpx.Client(timeout=timeout, verify=False, follow_redirects=True) as c:
            # stream + read only first chunk: live-stream URLs never end,
            # so c.get() would download forever. Cap at 8 KB then close.
            with c.stream("GET", e.url, headers={"User-Agent": DEFAULT_UA}) as r:
                body = b""
                for chunk in r.iter_bytes(8192):
                    body = chunk
                    break
                return e, classify_body(r.status_code,
                                        r.headers.get("content-type", ""), body)
    except Exception:  # noqa: BLE001
        return e, "dead"


def check_all(entries, *, timeout=6, workers=70, open_filter_ad=True, on_log=None):
    out = []
    total = len(entries)
    step = max(1, total // 20)  # ~20 progress lines regardless of size
    if on_log:
        on_log(f"http check: 0/{total}")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_check_one, e, timeout) for e in entries]
        for i, fut in enumerate(as_completed(futs), 1):
            e, status = fut.result()
            if status == "ok":
                out.append(e)
            elif status == "ad" and not open_filter_ad:
                out.append(e)
            if on_log and (i % step == 0 or i == total):
                on_log(f"http check: {i}/{total} (reachable={len(out)})")
    return out
