from urllib.parse import quote, urljoin, urlparse

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

router = APIRouter(prefix="/api")

_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
       "AppleWebKit/605.1.15")


def _proxied(u: str) -> str:
    return "/api/proxy?url=" + quote(u, safe="")


def _rewrite_m3u8(text: str, base: str) -> str:
    # ponytail: rewrites URI lines + EXT-X-KEY/MEDIA URI attrs; covers common
    # HLS. Exotic tags (MAP, PART) pass through unrewritten — add if needed.
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            out.append(line)
        elif s.startswith("#"):
            if 'URI="' in s:
                pre, rest = s.split('URI="', 1)
                uri, post = rest.split('"', 1)
                out.append(f'{pre}URI="{_proxied(urljoin(base, uri))}"{post}')
            else:
                out.append(line)
        else:
            out.append(_proxied(urljoin(base, s)))
    return "\n".join(out)


@router.get("/proxy")
async def proxy(url: str, request: Request):
    if urlparse(url).scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="only http/https allowed")
    # ponytail: open-ish forwarder (SSRF ceiling) — fine for self-hosted LAN
    # tool; add host allowlist if ever exposed to untrusted callers.
    headers = {"User-Agent": _UA}
    rng = request.headers.get("range")
    if rng:
        headers["Range"] = rng

    client = httpx.AsyncClient(timeout=15, verify=False, follow_redirects=True)
    try:
        req = client.build_request("GET", url, headers=headers)
        r = await client.send(req, stream=True)
    except Exception as e:  # noqa: BLE001
        await client.aclose()
        raise HTTPException(status_code=502, detail=f"upstream error: {e}")

    ct = r.headers.get("content-type", "")
    is_m3u8 = url.split("?")[0].lower().endswith(".m3u8") or "mpegurl" in ct.lower()
    if is_m3u8:
        try:
            body = await r.aread()
        finally:
            await r.aclose()
            await client.aclose()
        text = body.decode("utf-8", errors="replace")
        rewritten = _rewrite_m3u8(text, str(r.url))
        return Response(content=rewritten,
                        media_type="application/vnd.apple.mpegurl")

    async def _iter():
        try:
            async for chunk in r.aiter_bytes(65536):
                yield chunk
        finally:
            await r.aclose()
            await client.aclose()

    resp_headers = {"Access-Control-Allow-Origin": "*"}
    return StreamingResponse(_iter(), status_code=r.status_code,
                             media_type=ct or "application/octet-stream",
                             headers=resp_headers)
