"""按 (频道, 主机) 的串播 / 内容不符黑名单。

IPTV 最难发现的问题不是死链，而是「名字对、内容不对」：CCTV5 的地址实际在播
CCTV6，广东卫视挂成了山东台。这类源在探测层面是完美的 —— HTTP 200、合法
m3u8、ffprobe 能出 1080p 视频流 —— 只有人肉看画面才能发现，因此只能靠人工
确认后写进黑名单。myTV 客户端用的也是这一套（APK assets/source_exclusions.json，
13 条 (channel_id, host) 记录 + 理由），这里把它搬到配置里。

配置（`config.yaml` → `filter.blocked_hosts`）：

    filter:
      blocked_hosts:
        CCTV5:
          183.250.156.180: 实测串播 CCTV6
          113.98.11.46: 实测串播 CCTV5+
        CCTV13:
          - ali-m-l.cztv.com          # 列表写法：不写理由
        CCTV9:
          "*.some-host.com": 整段主机都不对

键是规范化之后的频道名（normalize 阶段的 aliases/templates 跑完之后的名字），
值可以是 `主机: 理由` 映射，也可以直接是主机列表。主机名大小写不敏感、忽略
端口与末尾点，支持 `*.example.com` 通配子域。命中即从本次结果里剔除，并且
在运行日志里打印命中的频道@主机 + 理由，方便事后复核。
"""

from urllib.parse import urlsplit

HTTP_SCHEMES = ("http://", "https://")


def host_of(url: str) -> str:
    """URL 的主机名：小写、去端口、去末尾点、去 userinfo。

    `udp://@239.0.0.1:1234` 这类组播地址的 `@` 前缀必须剥掉，否则规则永远
    对不上；IPv6 的方括号同样要处理。
    """
    try:
        netloc = urlsplit(url or "").netloc
    except ValueError:
        return ""
    host = netloc
    if "@" in host:
        host = host.rsplit("@", 1)[1]
    if host.startswith("["):  # [::1]:8080
        end = host.find("]")
        host = host[1:end] if end > 0 else host[1:]
    elif ":" in host:
        host = host.rsplit(":", 1)[0]
    return host.strip().lower().rstrip(".")


def _clean_host(host) -> str:
    return str(host or "").strip().lower().rstrip(".")


def normalize_rules(raw) -> dict[str, dict[str, str]]:
    """把配置里的规则整理成 `{频道名(casefold): {主机规则: 理由}}`。

    容忍三种写法（映射 / 列表 / 单个字符串），坏数据一律跳过而不是报错：
    一条手写错的规则不应该让整轮更新失败。
    """
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for chan, val in raw.items():
        name = str(chan or "").strip().casefold()
        if not name:
            continue
        hosts: dict[str, str] = {}
        if isinstance(val, dict):
            for host, reason in val.items():
                h = _clean_host(host)
                if h:
                    hosts[h] = str(reason or "").strip()
        elif isinstance(val, (list, tuple, set)):
            for host in val:
                h = _clean_host(host)
                if h:
                    hosts.setdefault(h, "")
        else:
            h = _clean_host(val)
            if h:
                hosts[h] = ""
        if hosts:
            out[name] = hosts
    return out


def match_host(host_rules: dict[str, str], host: str) -> str | None:
    """命中返回理由（可能是空串），未命中返回 None。"""
    if not host_rules or not host:
        return None
    for rule, reason in host_rules.items():
        if rule.startswith("*."):
            base = rule[2:]
            if base and (host == base or host.endswith("." + base)):
                return reason
        elif host == rule:
            return reason
    return None


def apply(entries, rules: dict[str, dict[str, str]]):
    """返回 (保留的 entries, [(被剔除的 entry, 理由)])。"""
    if not rules:
        return entries, []
    kept, dropped = [], []
    for e in entries:
        reason = match_host(rules.get(str(e.name or "").strip().casefold(), {}),
                            host_of(e.url))
        if reason is None:
            kept.append(e)
        else:
            dropped.append((e, reason))
    return kept, dropped
