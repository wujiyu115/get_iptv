#!/usr/bin/env python3
"""
iptv_cn.py — 国内 IPTV 播放源：抓取 → 去重 → 测试 → 输出
================================================================
一键运行:  python3 iptv_cn.py

数据来源 (3 个开源项目):
  1. iptv-org/iptv        — 社区维护 IPTV 目录 (中国频道)
  2. Guovin/iptv-api (gd) — 自动测试+分类的国内源 (最有价值)
  3. YanG-1989/m3u        — 手动聚合 + 咪咕移动源

输出文件:
  cn_iptv_full.m3u     — 完整版 (所有可用 URL，含备用源)
  cn_iptv_compact.m3u  — 精简版 (每频道取最佳源)
  cn_iptv_tvbox.txt    — TVBox/DIYP 格式
"""
import os, re, ssl, json, time, subprocess
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen

# ======================== 配置 ========================
BASE   = os.path.dirname(os.path.abspath(__file__))
SRC    = os.path.join(BASE, "sources")
OUT    = BASE
UA     = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# 原始数据源 (文件名, URL, 说明)
SOURCES = [
    ("iptv-org-cn.m3u",
     "https://iptv-org.github.io/iptv/countries/cn.m3u",
     "iptv-org 中国频道"),
    ("guovin-gd-result.m3u",
     "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u",
     "Guovin 已测试国内源"),
    ("guovin-gd-result.txt",
     "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.txt",
     "Guovin 已测试国内源 (txt)"),
    ("yang-gather.m3u",
     "https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u",
     "YanG 聚合国内源"),
    ("yang-migu.m3u",
     "https://raw.githubusercontent.com/YanG-1989/m3u/main/Migu.m3u",
     "YanG 咪咕移动源"),
]

# 解析时跳过的非频道条目
SKIP_NAMES = ["温馨提示", "免费订阅", "维护", "使用说明", "Github", "更新时间"]

# 清洗时过滤的杂质
JUNK_GROUPS = {"Religious", "Undefined", "News", "General", "Kids",
                "Business", "Sports", "Lifestyle", "Movies", "Culture"}
JUNK_NAMES  = ["更新时间", "Bread TV", "ABN China", "2026-07"]

# 测试参数
HTTP_TIMEOUT    = 6
HTTP_WORKERS    = 70
FFPROBE_TIMEOUT = 10
FFPROBE_WORKERS = 25

# 频道分组排序优先级
GROUP_ORDER = ["📺央", "💰央视", "📡卫视", "🌊港", "🏀体育",
               "🎬电影", "🏛经典", "🪁动画", "☘️", "🎵", "游戏"]


# ======================== 步骤 1: 抓取 ========================
def step1_fetch():
    print("\n{'='*60}")
    print("  步骤 1/4: 抓取原始数据源")
    print(f"{'='*60}")
    os.makedirs(SRC, exist_ok=True)
    ok = fail = 0
    t0 = time.time()
    for name, url, desc in SOURCES:
        dest = os.path.join(SRC, name)
        print(f"  ↓ {name:28s} [{desc}]")
        try:
            req = Request(url, headers={"User-Agent": UA})
            with urlopen(req, timeout=90) as resp, open(dest, "wb") as f:
                data = resp.read()
                f.write(data)
            if len(data) < 50:
                os.remove(dest)
                print(f"    ✗ 内容过小 ({len(data)}B)，可能已失效")
                fail += 1
            else:
                print(f"    ✓ {len(data):,} bytes")
                ok += 1
        except Exception as e:
            print(f"    ✗ 失败: {e}")
            if os.path.exists(dest): os.remove(dest)
            fail += 1
    print(f"\n  完成: {ok} 成功, {fail} 失败, 耗时 {time.time()-t0:.0f}s")
    return ok


# ======================== 步骤 2: 解析+去重 ========================
def parse_m3u(path):
    """解析 m3u → [{name,url,logo,group,tvg_id,tvg_name,source}]"""
    entries = []
    cur = {}
    try:
        for line in open(path, encoding="utf-8", errors="replace"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("#EXTINF"):
                cur = {"name": "", "logo": "", "group": "", "tvg_id": "",
                       "tvg_name": "", "source": os.path.basename(path)}
                m = re.search(r',(.+)$', line);         cur["name"]    = m.group(1).strip() if m else ""
                m = re.search(r'tvg-logo="([^"]*)"', line);  cur["logo"]    = m.group(1) if m else ""
                m = re.search(r'group-title="([^"]*)"', line); cur["group"]   = m.group(1) if m else ""
                m = re.search(r'tvg-id="([^"]*)"', line);    cur["tvg_id"]   = m.group(1) if m else ""
                m = re.search(r'tvg-name="([^"]*)"', line);  cur["tvg_name"] = m.group(1) if m else ""
            elif line.startswith("#"):
                continue
            elif line.startswith(("http://", "https://", "rtmp://", "rtsp://", "udp://")):
                if cur.get("name") and not any(k in cur["name"] for k in SKIP_NAMES):
                    cur["url"] = line
                    entries.append(cur)
                cur = {}
    except Exception as e:
        print(f"  解析错误 {path}: {e}")
    return entries


def step2_parse_dedup():
    print(f"\n{'='*60}")
    print("  步骤 2/4: 解析 + 去重")
    print(f"{'='*60}")
    all_e = []
    import glob
    for fp in sorted(glob.glob(os.path.join(SRC, "*.m3u"))):
        es = parse_m3u(fp)
        print(f"  {os.path.basename(fp):28s} {len(es):5d} 条")
        all_e.extend(es)
    print(f"\n  原始合计: {len(all_e)}")

    # URL 去重 (小写化 scheme+host)
    seen = set()
    deduped = []
    for e in all_e:
        u = e["url"].strip().lower()
        if u not in seen:
            seen.add(u)
            deduped.append(e)
    print(f"  去重后:   {len(deduped)}  (移除 {len(all_e) - len(deduped)} 重复)")
    return deduped


# ======================== 步骤 3: HTTP 筛选 ========================
def http_check(e):
    url = e["url"]
    if not url.startswith(("http://", "https://")):
        return (e, "skip")
    try:
        r = urlopen(Request(url, headers={"User-Agent": UA}), timeout=HTTP_TIMEOUT, context=SSL_CTX)
        code = r.getcode()
        body = r.read(8192)
        bs = body.decode("utf-8", errors="replace").lower()
        if code == 200 and ("#extm3u" in bs or "#extinf" in bs or
                            "video" in r.headers.get("content-type", "").lower() or
                            len(body) > 200):
            return (e, "ok")
        return (e, "dead")
    except:
        return (e, "dead")


def step3_http_filter(deduped):
    print(f"\n{'='*60}")
    print(f"  步骤 3a: HTTP 可达性检测 ({len(deduped)} URL, {HTTP_WORKERS} 并发, {HTTP_TIMEOUT}s)")
    print(f"{'='*60}")
    survivors = []
    dead = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=HTTP_WORKERS) as ex:
        for fut in as_completed({ex.submit(http_check, e): e for e in deduped}):
            e, st = fut.result()
            if st in ("ok", "skip"):
                survivors.append(e)
            else:
                dead += 1
    print(f"  可达: {len(survivors)}  死链: {dead}  ({time.time()-t0:.0f}s)")
    return survivors


# ======================== 步骤 3b: ffprobe 测试 ========================
def ffprobe_test(e):
    url = e["url"]
    cmd = ["ffprobe", "-hide_banner", "-v", "error", "-user_agent", "Mozilla/5.0",
           "-rw_timeout", "7000000", "-analyzeduration", "1500000", "-probesize", "1000000",
           "-show_entries", "stream=codec_type,codec_name,width,height",
           "-of", "json", url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=FFPROBE_TIMEOUT)
        if r.returncode == 0 and r.stdout.strip():
            d = json.loads(r.stdout)
            if d.get("streams"):
                vs = [s for s in d["streams"] if s.get("codec_type") == "video"]
                if vs:
                    s = vs[0]
                    w = s.get("width", 0) or 0
                    h = s.get("height", 0) or 0
                    return (e, "playable", f"{s.get('codec_name','?')} {w}x{h}", h)
                return (e, "playable", "audio", 0)
            return (e, "fail", "no-streams", 0)
        return (e, "fail", (r.stderr or "")[:40].replace("\n", " "), 0)
    except subprocess.TimeoutExpired:
        return (e, "fail", "timeout", 0)
    except Exception as ex:
        return (e, "fail", str(ex)[:30], 0)


def step3b_ffprobe(survivors):
    print(f"\n{'='*60}")
    print(f"  步骤 3b: ffprobe 播放确认 ({len(survivors)} URL, {FFPROBE_WORKERS} 并发, {FFPROBE_TIMEOUT}s)")
    print(f"{'='*60}")
    results = []
    playable = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=FFPROBE_WORKERS) as ex:
        for fut in as_completed({ex.submit(ffprobe_test, e): e for e in survivors}):
            e, st, detail, res = fut.result()
            results.append({**e, "status": st, "detail": detail, "resolution": res})
            if st == "playable":
                playable += 1
            if len(results) % 100 == 0:
                print(f"  [{len(results)}/{len(survivors)}] 可播={playable} ({time.time()-t0:.0f}s)")
    print(f"  可播: {playable}/{len(survivors)}  ({time.time()-t0:.0f}s)")
    return results


# ======================== 步骤 4: 清洗+输出 ========================
def group_sort_key(g):
    for i, pfx in enumerate(GROUP_ORDER):
        if g.startswith(pfx) or (pfx == "游戏" and "游戏" in g):
            return i
    return len(GROUP_ORDER)


def step4_output(results):
    print(f"\n{'='*60}")
    print("  步骤 4: 清洗 + 输出")
    print(f"{'='*60}")
    play = [e for e in results if e["status"] == "playable"]

    # 过滤杂质
    clean = []
    for e in play:
        g = e.get("group", "") or ""
        n = e["name"]
        if g in JUNK_GROUPS and not re.search(r'[\u4e00-\u9fff]', n):
            continue
        if any(k in n for k in JUNK_NAMES):
            continue
        clean.append(e)
    print(f"  清洗: {len(clean)} 条 (移除 {len(play)-len(clean)} 杂质)")

    # 按频道名分组，每个频道的 URL 按清晰度降序
    by_name = defaultdict(list)
    for e in clean:
        by_name[e["name"]].append(e)
    for name in by_name:
        by_name[name].sort(key=lambda x: -x.get("resolution", 0))

    # --- 完整版 m3u (所有可用 URL) ---
    clean.sort(key=lambda r: (group_sort_key(r.get("group", "")), r["name"], -r.get("resolution", 0)))
    lines = ["#EXTM3U"]
    for e in clean:
        g = e.get("group", "") or "其他"
        nm = e["name"]
        d = e.get("detail", "")
        tag = f" [{d}]" if d else ""
        lines.append(f'#EXTINF:-1 tvg-id="{e.get("tvg_id","")}" tvg-name="{e.get("tvg_name",nm)}" '
                     f'tvg-logo="{e.get("logo","")}" group-title="{g}",{nm}{tag}')
        lines.append(e["url"])
    path_full = os.path.join(OUT, "cn_iptv_full.m3u")
    open(path_full, "w", encoding="utf-8").write("\n".join(lines))

    # --- 精简版 m3u (每频道取最佳源) ---
    compact = []
    for name in sorted(by_name.keys(), key=lambda n: (group_sort_key(by_name[n][0].get("group", "")), n)):
        compact.append(by_name[name][0])
    compact.sort(key=lambda r: (group_sort_key(r.get("group", "")), r["name"]))
    lines2 = ["#EXTM3U"]
    for e in compact:
        g = e.get("group", "") or "其他"
        nm = e["name"]
        d = e.get("detail", "")
        tag = f" [{d}]" if d else ""
        lines2.append(f'#EXTINF:-1 tvg-id="{e.get("tvg_id","")}" tvg-name="{e.get("tvg_name",nm)}" '
                      f'tvg-logo="{e.get("logo","")}" group-title="{g}",{nm}{tag}')
        lines2.append(e["url"])
    path_compact = os.path.join(OUT, "cn_iptv_compact.m3u")
    open(path_compact, "w", encoding="utf-8").write("\n".join(lines2))

    # --- TVBox/DIYP txt ---
    txt_lines = []
    cur_group = ""
    for e in compact:
        g = e.get("group", "") or "其他"
        if g != cur_group:
            if cur_group:
                txt_lines.append("")
            txt_lines.append(f"{g},#genre#")
            cur_group = g
        txt_lines.append(f"{e['name']},{e['url']}")
    path_txt = os.path.join(OUT, "cn_iptv_tvbox.txt")
    open(path_txt, "w", encoding="utf-8").write("\n".join(txt_lines))

    # --- 统计 ---
    gc = Counter(e.get("group", "") or "其他" for e in clean)
    rc = Counter()
    for e in clean:
        h = e.get("resolution", 0)
        if h >= 1080: rc["1080p+"] += 1
        elif h >= 720: rc["720p"] += 1
        elif h >= 480: rc["480p"] += 1
        else: rc["SD/other"] += 1

    print(f"\n{'='*60}")
    print("  ✅ 完成!")
    print(f"{'='*60}")
    print(f"\n  完整版: {len(clean)} 条流 / {len(by_name)} 个频道  → cn_iptv_full.m3u     ({os.path.getsize(path_full)//1024}KB)")
    print(f"  精简版: {len(compact)} 个频道 (每频道最佳源)   → cn_iptv_compact.m3u  ({os.path.getsize(path_compact)//1024}KB)")
    print(f"  TVBox:  {len(compact)} 个频道                  → cn_iptv_tvbox.txt     ({os.path.getsize(path_txt)//1024}KB)")
    print(f"\n  {'分组':20s} {'流数':>5s} / {'频道':>4s}")
    print(f"  {'-'*35}")
    for g, c in sorted(gc.items(), key=lambda x: group_sort_key(x[0])):
        uniq = len(set(e["name"] for e in clean if (e.get("group", "") or "其他") == g))
        print(f"  {g:20s} {c:5d} / {uniq:4d}")
    print(f"\n  清晰度: " + "  ".join(f"{r} {c}" for r, c in rc.most_common()))


# ======================== 主入口 ========================
def main():
    print("=" * 60)
    print("  国内 IPTV 播放源 — 抓取→去重→测试→输出")
    print("=" * 60)
    t_start = time.time()

    step1_fetch()
    deduped = step2_parse_dedup()
    survivors = step3_http_filter(deduped)
    results = step3b_ffprobe(survivors)
    step4_output(results)

    print(f"\n  总耗时: {time.time()-t_start:.0f}s")


if __name__ == "__main__":
    main()
