"""首分片大小当码率代理：ffprobe 之前的廉价一票。

myTV 客户端在端上就是这么做的（`SourceUpdater.probe` / `probeLen`，阈值
`MIN_SEG_KB=80`）：不跑 ffmpeg，只拉一次 playlist（≤96 KB）+ 首条分片的前
256 KB，用拿到的字节数当码率 / 通断代理。对我们有两个用处：

1. 在 ffprobe 之前把「连分片都拉不下来」的线路剔掉 —— ffprobe 是 25 并发 ×
   10 s 的重活，提前筛掉能省掉大半无效探测；
2. playlist 里声明的 `RESOLUTION` 顺手填进 `resolution`，这样即使关掉
   ffprobe，`filter.min_resolution` 也还有东西可判断。

注意这是**下限检测**，不是真码率：测的是「限定时间内首分片能拿到多少 KB」，
所以它适合剔死链 / 极慢线路，不适合当画质门槛（画质仍由 ffprobe + min_resolution
负责）。拿不到测量值的条目一律放行（seg_kb=0 视为未测），避免探测抖动误杀。
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

import httpx

from pipeline.fetch import resolve_ua
from pipeline.models import Entry, RunCancelled

MAX_PLAYLIST_BYTES = 96 * 1024   # playlist 声明部分够用，别拉整份
MAX_SEG_BYTES = 256 * 1024       # 单条最多读这么多分片字节
SEG_WINDOW_S = 1.2               # 只统计这段时间内能拿到多少（吞吐下限）
MAX_VARIANT_DEPTH = 3            # master playlist 最多下钻几层
HTTP_SCHEMES = ("http://", "https://")

_ATTR = re.compile(r'([A-Za-z0-9-]+)=("[^"]*"|[^,]*)')


def parse_attrs(line: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in _ATTR.findall(line or ""):
        out[k.upper()] = v.strip().strip('"').strip()
    return out


def _height(res: str) -> int:
    m = re.match(r"\s*\d+\s*[xX]\s*(\d+)", res or "")
    return int(m.group(1)) if m else 0


def pick_best_variant(text: str, base_url: str) -> tuple[str, int]:
    """master playlist 里挑最高清变体（同高按带宽）。返回 (url, 高度)。

    不是 master、或解析不到任何变体时返回 ("", 0)。
    """
    lines = text.splitlines()
    best_url, best_h, best_bw = "", 0, 0
    for i, line in enumerate(lines):
        s = line.strip()
        if not s.upper().startswith("#EXT-X-STREAM-INF"):
            continue
        attrs = parse_attrs(s)
        h = _height(attrs.get("RESOLUTION", ""))
        try:
            bw = int(attrs.get("BANDWIDTH", "0") or 0)
        except ValueError:
            bw = 0
        uri = next((x.strip() for x in lines[i + 1:]
                    if x.strip() and not x.strip().startswith("#")), "")
        if not uri:
            continue
        if (h, bw) > (best_h, best_bw):
            best_url, best_h, best_bw = urljoin(base_url, uri), h, bw
    return best_url, best_h


def first_segment(text: str, base_url: str) -> str:
    """媒体 playlist 里第一条分片的绝对地址（跳过 #EXT-X-MAP 等标签行）。"""
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        return urljoin(base_url, s)
    return ""


def _read(resp, cap: int, deadline: float) -> bytes:
    buf = bytearray()
    for chunk in resp.iter_bytes(8192):
        if not chunk:
            continue
        buf += chunk[: cap - len(buf)]
        if len(buf) >= cap or time.monotonic() > deadline:
            break
    return bytes(buf)


def _fetch_playlist(client, url: str, ua: str, deadline: float):
    """返回 (文本, 最终 URL)；不是文本型 playlist 时返回 (None, url)。

    redirect 后的地址必须带回：生成器式地址（`live.php?id=X` 302 到
    `/live/CCTV1/index.m3u8`）里的分片是相对最终路径的，拿原始地址拼会错。
    """
    with client.stream("GET", url, headers={"User-Agent": ua}) as r:
        if r.status_code >= 400:
            return None, url
        final = str(r.url)
        if not final.lower().startswith(HTTP_SCHEMES):
            final = url
        return _read(r, MAX_PLAYLIST_BYTES, deadline).decode(
            "utf-8", errors="replace"), final


def _measure_segment(client, url: str, ua: str, timeout: int) -> tuple[int, bool]:
    """返回 (窗口内拿到的 KB, 是否确定已死)。

    只读 SEG_WINDOW_S 这么一段，不做整段下载：快线会直接撞上 MAX_SEG_BYTES
    上限，慢线拿到多少算多少。HTTP >= 400 是确定性的坏（分片 404/403/5xx），
    而超时 / 连接错误属于「不知道」，所以后者不算死，避免误杀。
    """
    with client.stream("GET", url, headers={"User-Agent": ua}) as r:
        if r.status_code >= 400:
            return 0, True
        deadline = time.monotonic() + min(timeout, SEG_WINDOW_S)
        return len(_read(r, MAX_SEG_BYTES, deadline)) // 1024, False


def probe_entry(e: Entry, timeout: int = 5) -> Entry:
    """测一条：填 `seg_kb` / `seg_dead`，能填就填 `resolution`。

    任何超时或异常都按「没测到」处理 —— 这一层只做筛除建议，存活判定归 check_http。
    """
    if not e.url.lower().startswith(HTTP_SCHEMES):
        return e  # rtmp/rtsp/udp 没有 playlist 概念，不参与
    ua = resolve_ua(e.ua)
    try:
        with httpx.Client(timeout=timeout, verify=False, follow_redirects=True) as c:
            # playlist 和分片各自有独立超时：共用一条 deadline 会让 playlist
            # 慢一点的源永远测不到分片。
            text, url = _fetch_playlist(c, e.url, ua,
                                        time.monotonic() + timeout)
            if not text or "#EXT" not in text:
                return e  # 不是 HLS playlist（或读不到）：不测、不判
            for _ in range(MAX_VARIANT_DEPTH):
                vurl, vheight = pick_best_variant(text, url)
                if not vurl:
                    break
                url = vurl
                if vheight and not e.resolution:
                    e.resolution = vheight
                text, final = _fetch_playlist(c, url, ua,
                                              time.monotonic() + timeout)
                if not text:
                    return e
                url = final
            seg = first_segment(text, url)
            if not seg:
                return e
            e.seg_kb, e.seg_dead = _measure_segment(c, seg, ua, timeout)
            return e
    except Exception:  # noqa: BLE001 - 单条失败不影响整批
        return e


def check_all(entries, *, timeout=5, workers=25, enabled=False, on_log=None,
              should_cancel=None):
    if not enabled:
        if on_log:
            on_log("segment probe disabled — skipping")
        return entries
    total = len(entries)
    step = max(1, total // 20)  # ~20 progress lines regardless of size
    if on_log:
        on_log(f"segment probe: 0/{total}")
    measured = 0
    dead = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(probe_entry, e, timeout) for e in entries]
        for i, fut in enumerate(as_completed(futs), 1):
            if should_cancel and should_cancel():
                for f in futs:
                    f.cancel()
                raise RunCancelled()
            e = fut.result()
            if e.seg_kb:
                measured += 1
            if e.seg_dead:
                dead += 1
            if on_log and (i % step == 0 or i == total):
                on_log(f"segment probe: {i}/{total} (measured={measured}, dead={dead})")
    return entries
