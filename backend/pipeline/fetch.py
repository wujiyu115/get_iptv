import httpx

DEFAULT_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
              "AppleWebKit/605.1.15")


def resolve_ua(ua: str = "") -> str:
    """Single place deciding which User-Agent a request uses: the entry's own
    UA when the playlist specified one, else DEFAULT_UA.

    Upstreams disagree about who may read them — the migu `live.php` generator
    answers only iPhone/APTV UAs and returns 404 for a generic `Mozilla/5.0` —
    so fetch, both check stages and the proxy must agree instead of each
    hard-coding its own string.
    """
    return (ua or "").strip() or DEFAULT_UA


# Responses smaller than this are treated as failures (empty/error pages).
MIN_CONTENT_BYTES = 20


def fetch_one(source: dict, *, user_agent: str = "", timeout: int = 10,
              retries: int = 2, http_proxy: str = ""):
    ua = user_agent or DEFAULT_UA
    proxy = http_proxy if source.get("use_proxy") and http_proxy else None
    for _ in range(retries + 1):
        try:
            with httpx.Client(timeout=timeout, verify=False, follow_redirects=True,
                              proxy=proxy) as client:
                r = client.get(source["url"], headers={"User-Agent": ua})
                r.raise_for_status()
                text = r.text
                if len(text) < MIN_CONTENT_BYTES:
                    continue
                return source, text
        except Exception:  # noqa: BLE001 - single source must not abort batch
            continue
    return source, None


def fetch_all(sources, *, user_agent: str = "", timeout: int = 10, retries: int = 2,
              http_proxy: str = "", on_log=None):
    out = []
    for src in sources:
        s, text = fetch_one(src, user_agent=user_agent, timeout=timeout,
                            retries=retries, http_proxy=http_proxy)
        if text is not None:
            out.append((s, text))
            if on_log:
                on_log(f"fetch ok: {s['name']} ({len(text)} bytes)")
        elif on_log:
            on_log(f"fetch FAIL: {s['name']}")
    return out
