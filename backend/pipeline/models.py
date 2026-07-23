from dataclasses import dataclass, field


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
