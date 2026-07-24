import asyncio
import shutil
from urllib.parse import quote, urljoin, urlparse

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

router = APIRouter(prefix="/api")

_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
       "AppleWebKit/605.1.15")


def _ffmpeg_restream_cmd(url: str) -> list[str]:
    # Transcode the source into a clean continuous MPEG-TS. Stream-copy is not
    # enough: these streams reference H.264 parameter sets (PPS) that are never
    # sent in-band, so copied frames stay undecodable and browser MSE stalls.
    # Re-encoding forces ffmpeg's tolerant decoder to rebuild valid H.264/AAC
    # with proper SPS/PPS. ultrafast + zerolatency keeps it ~realtime.
    return ["ffmpeg", "-hide_banner", "-loglevel", "error",
            "-user_agent", _UA,
            "-analyzeduration", "2000000", "-probesize", "5000000",
            "-fflags", "+genpts", "-i", url,
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
            "-c:a", "aac", "-ac", "2",
            "-f", "mpegts", "-"]


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
        # A live playlist is a sliding window: the player must re-fetch it to see
        # new segments. Without no-store the browser serves a cached (stale)
        # playlist on refresh, so old segment names 404 and playback stalls after
        # the initial buffer (~10s).
        return Response(content=rewritten,
                        media_type="application/vnd.apple.mpegurl",
                        headers={"Cache-Control": "no-store, no-cache, must-revalidate",
                                 "Access-Control-Allow-Origin": "*"})

    async def _iter():
        try:
            async for chunk in r.aiter_bytes(65536):
                yield chunk
        finally:
            await r.aclose()
            await client.aclose()

    # Forward range/length headers so a 206 stays coherent: a partial response
    # without Content-Range makes byte-range players (mpegts.js, <video>) abort.
    resp_headers = {"Access-Control-Allow-Origin": "*",
                    "Accept-Ranges": "bytes"}
    for h in ("content-range", "accept-ranges", "content-length"):
        v = r.headers.get(h)
        if v:
            resp_headers[h.title()] = v
    return StreamingResponse(_iter(), status_code=r.status_code,
                             media_type=ct or "application/octet-stream",
                             headers=resp_headers)


@router.get("/restream")
async def restream(url: str):
    # Compatibility path for streams that stall in browser HLS: ffmpeg remuxes the
    # source into a continuous MPEG-TS the frontend plays via mpegts.js.
    if urlparse(url).scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="only http/https allowed")
    if not shutil.which("ffmpeg"):
        raise HTTPException(status_code=501, detail="ffmpeg not available")

    proc = await asyncio.create_subprocess_exec(
        *_ffmpeg_restream_cmd(url),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)

    async def _iter():
        try:
            while True:
                chunk = await proc.stdout.read(65536)
                if not chunk:
                    break
                yield chunk
        finally:
            # client disconnected or stream ended — don't leave ffmpeg running
            if proc.returncode is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                await proc.wait()

    return StreamingResponse(_iter(), media_type="video/mp2t",
                             headers={"Access-Control-Allow-Origin": "*",
                                      "Cache-Control": "no-store"})
