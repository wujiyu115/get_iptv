# IPTV 聚合服务

自动抓取、检测、聚合多个 IPTV 直播源，输出干净可用的播放列表，并提供带在线播放的 Web 管理界面。

从多个上游源（m3u / txt）拉取频道，做频道名归一化、去重、可用性检测（HTTP + ffprobe 实际探流）、按清晰度/速度排序过滤，最终生成 `full.m3u` / `compact.m3u` / `iptv.txt`，支持定时更新与失效源自动禁用。

---

## 特性

- **多源聚合**：支持 m3u 与 txt 两种源格式，内置一批活跃的默认源。
- **频道归一化**：通过别名（正则/精确）与模板统一频道名、分组、台标、排序。
- **按条目的 UA**：读取 m3u 的 `http-user-agent`，检测、探测、入库、回填、播放全链路沿用同一个 UA（缺失则回落到默认 UA），并在输出的 m3u 里带回该属性。有些上游（如咪咕 `live.php` 生成器）只认特定 UA，其它一律 404。
- **两级可用性检测**：
  - HTTP 检测（并发）——过滤死链、广告占位。
  - ffprobe 实际探流——确认可播放，识别分辨率/编码，估算速度与延迟。
- **串播黑名单**：`filter.blocked_hosts` 按 (频道, 主机) 排除“名字对、内容不对”的源（CCTV5 在播 CCTV6 这类，探测层面看不出来），命中会在日志里写清理由；探测前生效，历史回填项同样过滤。
- **首分片粗筛（可选）**：`check.segment_probe` 打开后，在 ffprobe 之前只拉 playlist + 首条分片，用 1.2 秒内拿到的 KB 数做吞吐下限、顺便从 playlist 补齐分辨率；`filter.min_seg_kb` 据此剔除拉不动分片的线路（默认关闭）。
- **过滤排序**：按最低分辨率、最低速度、清晰度/速度排序，限制每频道 URL 数。
- **历史合并**：本次未采到的频道可从上次成功结果回填，减少抖动；默认先对回填项重检存活（`history_recheck`），避免把上一轮已过期的签名 URL 继续发布出去。
- **定时更新**：`interval`（间隔小时）或 `time`（每日定点）两种调度模式。
- **失效源自动禁用**：连续失效达阈值（5 次）自动停用；界面重新启用时自动清零计数。
- **Web 管理界面**：源 / 别名 / 模板管理，任务运行与实时日志，频道搜索/分组/在线试播，运行报告。
- **在线播放**：内置流代理绕过 CORS/混合内容；hls.js / mpegts.js 播放；对浏览器 MSE 播不动的问题流，自动回退到 ffmpeg 转封装兼容播放。
- **抓取代理**：界面可配置 HTTP 代理（存数据库，无需改配置文件）。
- **源更新时间**：对 GitHub 源可按需查询最近提交时间。

---

## 技术栈

- 后端：Python 3.13 · FastAPI · APScheduler · httpx · ffmpeg/ffprobe
- 前端：React 18 · rsbuild（bun 构建）· hls.js · mpegts.js
- 存储：SQLite
- 打包：单容器（前端静态资源由后端一并服务）

---

## 快速开始（Docker）

镜像：`wujiyu115/get_iptv`

### docker compose（推荐）

```bash
git clone https://github.com/wujiyu115/get_iptv.git
cd get_iptv
docker compose up -d
```

打开 `http://localhost:5180`。

`docker-compose.yml` 默认挂载：

| 宿主机 | 容器内 | 用途 |
|---|---|---|
| `./config.yaml` | `/app/config.yaml` | 配置文件 |
| `./data` | `/app/data` | SQLite 数据库 |
| `./output` | `/app/output` | 生成的播放列表 |

> compose 默认 `build: .` 本地构建。若想直接用发布镜像，把该行改为 `image: wujiyu115/get_iptv:latest`。

### docker run

```bash
docker run -d --name iptv -p 5180:5180 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/output:/app/output \
  wujiyu115/get_iptv:latest
```

镜像已内置 ffmpeg（探流与转封装播放所需）。

---

## 使用指南

Web 界面（`http://localhost:5180`）分为几个面板：

- **抓取源**：增删源、启用/停用、是否走代理；查看失效次数与最近成功时间；点「更新」查询 GitHub 源的最近提交时间；「代理设置」配置抓取用的 HTTP 代理。
- **别名 / 模板**：配置频道名归一化规则与分组/台标/排序模板。
- **任务**：「运行一次」手动触发；运行中可「中断」；实时日志；配置调度（interval/time、时区、启动即跑）。
- **频道**：搜索、按分组浏览，点击在线试播。
- **报告**：本次运行的频道数、分组、清晰度分布、各源状态与运行历史。

### 输出地址

生成后可直接订阅：

- `http://localhost:5180/full.m3u` —— 完整列表
- `http://localhost:5180/compact.m3u` —— 精简列表
- `http://localhost:5180/iptv.txt` —— txt 格式

### 播放机制

浏览器播放经后端代理，避免 CORS 与混合内容问题：

- `.m3u8` → hls.js（Safari 走原生）；`.ts`/`.flv` → mpegts.js。
- 部分直播源分段缺失 H.264 参数集或时间戳不连续，浏览器 MSE 会卡。此时播放器在致命错误或约 6 秒卡顿后，自动切换到 `/api/restream`：后端用 ffmpeg 重编码为干净连续的 MPEG-TS 再播（仅在需要时启用，避免对正常源浪费 CPU）。

---

## 配置

编辑 `backend/config.yaml`（Docker 下为挂载的 `./config.yaml`，首次可从 `config.yaml.example` 复制）。主要项：

```yaml
schedule:
  update_mode: interval     # interval | time
  update_interval: 12       # interval 模式：每 N 小时
  update_times: []          # time 模式：["06:00","18:00"]
  update_startup: false     # 启动即跑一次
  time_zone: Asia/Shanghai
fetch:
  request_timeout: 10
  retries: 2
check:
  http_timeout: 6
  http_workers: 70
  ffprobe_enabled: true
  ffprobe_timeout: 10
  ffprobe_workers: 25
  segment_probe: false      # 首分片粗筛（ffprobe 之前，见下）
  segment_probe_timeout: 5
filter:
  urls_limit: 5             # 每频道保留 URL 数（0=不限）
  min_resolution: 1280x720
  min_speed: 0.5
  min_seg_kb: 0             # >0 才按首分片吞吐过滤（80 ≈ 死链下限，非画质门槛）
  sort_by: resolution,speed
  open_filter_ad: true
  open_history: true        # 历史回填
  history_recheck: true     # 回填项先重检存活（钉死动态签名 URL 的过期问题）
  blocked_hosts: {}         # 频道 -> {主机: 理由}，人工确认“串播/内容不符”后填写
output:
  dir: ./output
```

> 抓取用的 HTTP 代理不在此文件配置，改在界面「代理设置」里设置（存数据库，改后即时对下次抓取生效）。

#### 串播黑名单 `filter.blocked_hosts`

IPTV 里最坑的一类源不是死链，而是**名字对、内容不对** —— 标着 CCTV5 实际在播
CCTV6，广东卫视挂成了山东台。这种地址在探测眼里是完美的（HTTP 200、合法
m3u8、ffprobe 能出 1080p），只有人肉看画面才能发现，所以做成人工确认后落配置：

```yaml
filter:
  blocked_hosts:
    CCTV5:
      183.250.156.180: 实测串播 CCTV6      # 映射写法：带理由
      113.98.11.46: 实测串播 CCTV5+
    CCTV13:
      - ali-m-l.cztv.com                  # 列表写法：不带理由
    CCTV9:
      "*.bad-host.com": 整段主机都不对      # 支持通配子域
```

键是**规范化之后**的频道名（aliases/templates 跑完的名字），主机忽略端口、大小写、
末尾点；命中即丢弃，并在运行日志里打印 `频道 @ 主机 — 理由`。规则在探测之前
生效（不浪费探测预算），历史回填项也过一遍（规则可能是在上一次运行后才加的）。

#### 首分片粗筛 `check.segment_probe` + `filter.min_seg_kb`

仿 myTV 客户端的做法：不跑 ffmpeg，只拉一次 playlist（≤96 KB）+ 首条分片，
看 `1.2 秒内能拿到多少 KB`，用这个数当吞吐/码率下限。实测 223 条记录 **6.8 秒**
跑完（ffprobe 是 25 并发 × 10 秒的重活），适合做大范围初筛。

- `check.segment_probe: false` 默认关闭（不额外发请求）；打开后才测。
- `filter.min_seg_kb`：拿到 < N KB 或**分片明确报错（HTTP ≥ 400）**时剔除；
  `0` = 不按此项过滤。超时/异常算“没测到”，一律放行，避免探测抖动误杀。
- 顺手把 playlist 里声明的 `RESOLUTION` 填进 `resolution`，这样关掉 ffprobe 时
  `min_resolution` 还有东西可判。
- 它是**下限检测**，不是画质门槛：画质仍由 ffprobe + `min_resolution` 负责。

### 环境变量

| 变量 | 说明 | 默认 |
|---|---|---|
| `PORT` | 服务端口 | `5180` |
| `HOST` | 监听地址（dev） | `0.0.0.0` |
| `CONFIG_FILE` | 配置文件路径 | `backend/config.yaml` |
| `DB_PATH` | SQLite 路径 | `./data/iptv.db` |
| `OUTPUT_DIR` | 输出目录 | `./output` |
| `FRONTEND` | 前端 dist 目录（不设则纯 API） | — |
| `LOG_DIR` / `LOG_LEVEL` | 日志目录 / 级别 | `logs` / `INFO` |
| `GITHUB_TOKEN` | 查询源更新时间时提升 GitHub API 限额（60/时 → 5000/时） | — |

---

## 开发指南

依赖：[bun](https://bun.sh)（前端）、[uv](https://github.com/astral-sh/uv)（后端）、ffmpeg（探流/播放）。

### 一键起本地开发环境

```bash
./start_dev.sh            # 默认 5180 端口，可传参改端口：./start_dev.sh 8080
```

脚本会：构建前端并 watch、创建 Python venv 装依赖、以 reload 模式起后端。访问 `http://localhost:5180`。

### 分别运行

```bash
# 后端（自动 reload）
cd backend
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
python run_dev.py                  # 生产用 run_prod.py

# 前端
cd frontend
bun install
bun run dev                        # 或 bun run build 产出 dist
```

### 测试

改动代码后必须新增/更新测试并跑到全绿（见 `CLAUDE.md`）：

```bash
cd backend && python -m pytest tests/ -q
```

### 处理流程（pipeline）

`backend/pipeline/runner.py` 按序执行：

```
fetch → parse → normalize(aliases/templates) → dedup
      → block_hosts (可选，串播黑名单)
      → check_http → segment probe (可选，首分片粗筛) → check_ffprobe
      → filter_sort(min_resolution/min_speed/min_seg_kb)
      → history recheck (可选) → history merge
      → output(m3u/txt) → source auto-disable
```

### 目录结构

```
backend/
  app.py            FastAPI 应用（含前端静态托管）
  run_dev.py        开发入口（reload）
  run_prod.py       生产入口
  config/           配置加载
  db/               schema、seed、连接
  pipeline/         抓取→检测→输出各阶段
  routes/           API 路由（sources/tasks/channels/proxy/...）
  services/         业务逻辑（run/source/settings/github/report）
  scheduler/        APScheduler 定时任务
  tests/            pytest 测试
frontend/
  src/components/   各面板 React 组件
  src/api.ts        API 封装
Dockerfile          两阶段构建（前端 bun → 后端 python + ffmpeg）
docker-compose.yml
start_dev.sh        本地开发一键脚本
```

### API 速览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/sources` | 源列表；`POST/PUT/DELETE` 增改删 |
| GET | `/api/sources/{id}/github-updated` | 源的 GitHub 最近提交时间 |
| GET/PUT | `/api/settings/proxy` | 抓取 HTTP 代理 |
| POST | `/api/tasks/run` · `/api/tasks/stop` | 运行 / 中断任务 |
| GET | `/api/tasks/status` · `/api/tasks/logs` | 状态 / 实时日志(SSE) |
| GET/PUT | `/api/tasks/schedule` | 调度配置 |
| GET | `/api/channels` · `/api/reports` | 频道 / 报告 |
| GET | `/api/proxy?url=` · `/api/restream?url=` | 流代理 / ffmpeg 转封装 |
| GET | `/full.m3u` · `/compact.m3u` · `/iptv.txt` | 播放列表输出 |
