from dataclasses import dataclass


class RunCancelled(Exception):
    """Raised cooperatively when a run is asked to stop mid-flight."""


@dataclass
class Entry:
    name: str
    url: str
    logo: str = ""
    group: str = ""
    tvg_id: str = ""
    tvg_name: str = ""
    source: str = ""
    status: str = ""
    detail: str = ""
    resolution: int = 0
    speed: float = 0.0
    delay: float = 0.0
    # per-entry User-Agent from the playlist (m3u http-user-agent attr). Empty
    # means "use DEFAULT_UA". Some upstreams (e.g. the migu live.php generator)
    # 404 for any other UA, so this has to follow the entry all the way through
    # checking, storage, history backfill and playback.
    ua: str = ""
    # 首条分片在 SEG_WINDOW 内能拿到的字节数（KB），由 check_segment 测；0 = 未测。
    # 不落库：它只服务于当轮的 filter.min_seg_kb 粗筛。
    seg_kb: int = 0
    # playlist 正常、但首条分片明确报错（HTTP >= 400）时为 True。超时/异常
    # 不算（不确定，不能据此误杀）。
    seg_dead: bool = False
