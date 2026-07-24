import json
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from pipeline.models import Entry, RunCancelled

_PROBESIZE = 1_000_000  # bytes sampled; used to estimate speed


def ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


def build_cmd(url: str, timeout: int) -> list[str]:
    return ["ffprobe", "-hide_banner", "-v", "error", "-user_agent", "Mozilla/5.0",
            "-rw_timeout", str(int(timeout * 0.7 * 1_000_000)),
            "-analyzeduration", "1500000", "-probesize", str(_PROBESIZE),
            "-show_entries", "stream=codec_type,codec_name,width,height",
            "-of", "json", url]


def parse_probe_json(out: str) -> tuple[str, int]:
    try:
        streams = json.loads(out).get("streams", [])
    except Exception:  # noqa: BLE001
        return "parse-error", 0
    for s in streams:
        if s.get("codec_type") == "video":
            w, h = s.get("width", 0), s.get("height", 0)
            return f"{s.get('codec_name', '')} {w}x{h}", int(h or 0)
    if streams:
        return "audio", 0
    return "no-streams", 0


def _probe_one(e: Entry, timeout: int):
    t0 = time.monotonic()
    try:
        r = subprocess.run(build_cmd(e.url, timeout), capture_output=True,
                           text=True, timeout=timeout)
        elapsed = time.monotonic() - t0
        detail, h = parse_probe_json(r.stdout)
        if detail in ("no-streams", "parse-error"):
            return e, False
        e.detail = detail
        e.resolution = h
        e.delay = round(elapsed, 3)
        e.speed = round((_PROBESIZE / 1_000_000) / elapsed, 3) if elapsed > 0 else 0.0
        e.status = "playable"
        return e, True
    except subprocess.TimeoutExpired:
        return e, False
    except Exception:  # noqa: BLE001
        return e, False


def check_all(entries, *, timeout=10, workers=25, enabled=True, on_log=None,
              should_cancel=None):
    if not enabled or not ffprobe_available():
        if on_log:
            on_log("ffprobe disabled/missing — skipping playback confirmation")
        for e in entries:
            e.status = "unchecked"
        return entries
    out = []
    total = len(entries)
    step = max(1, total // 20)  # ~20 progress lines regardless of size
    if on_log:
        on_log(f"ffprobe: 0/{total}")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_probe_one, e, timeout) for e in entries]
        for i, fut in enumerate(as_completed(futs), 1):
            if should_cancel and should_cancel():
                for f in futs:
                    f.cancel()
                raise RunCancelled()
            e, ok = fut.result()
            if ok:
                out.append(e)
            if on_log and (i % step == 0 or i == total):
                on_log(f"ffprobe: {i}/{total} (playable={len(out)})")
    return out
