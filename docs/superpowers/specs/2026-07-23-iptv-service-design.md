# IPTV 聚合服务 — 设计文档

日期: 2026-07-23
状态: 待实现

## 1. 目标

把现有单文件脚本 `iptv_cn.py`(抓取→去重→HTTP检测→ffprobe→输出 m3u/txt)改造成一个可长期运行的服务:

- 有 Web 配置界面(源管理 / 任务控制+实时日志 / 频道列表+播放预览 / 统计报告)
- 死链两阶段检测(HTTP 可达 + ffprobe 播放确认)
- 输出 m3u / txt,对外直出播放地址(无代理转流)
- 抓取源可扩展、可配置(SQLite 存储,Web 增删改,首启种子)
- 定时抓取 + 检查(APScheduler)
- 单 Docker 镜像部署(含 ffmpeg)
- 借鉴 Guovin/iptv-api 的模板+别名归一、每频道 urls_limit、广告过滤、测速、阈值过滤、源自动停用、历史合并、EPG/台标、调度增强

非目标(明确排除): RTMP 推流 / 转码 / nginx、回放接口、组播/酒店源、归属地(location)/运营商(isp)过滤、公网地址重写(public_domain)、GUI 桌面软件、performance_mode 自动 CPU 调优。

## 2. 技术栈

仿参考项目 `/Users/yitouxiaomaolv/git/Frostcast` 布局与视觉:

- 后端: Python 3.13 + FastAPI + uvicorn + PyYAML + APScheduler + httpx。复用现有管线算法。
- 前端: React 18 + TypeScript + rsbuild + axios + mpegts.js。
- 持久化: SQLite(源、别名、模板、跑批历史、频道结果)。
- 实时日志: SSE(FastAPI StreamingResponse + 浏览器原生 EventSource,前端零新依赖)。
- 部署: 单 Docker 镜像(多阶段构建前端 dist,Python slim + ffmpeg 运行)。
- 开发工具: `uv`(Python venv + 依赖)、`bun`(前端依赖 + 构建),`start_dev.sh` 一键启动(仿 Frostcast)。

## 3. 目录结构

```
get_iptv/
  backend/
    app.py                   # create_app: FastAPI, CORS, 挂路由, SPA fallback, 启动 scheduler
    run_dev.py / run_prod.py
    requirements.txt
    config.yaml(.example)
    config/config_loader.py  # yaml + 环境变量覆盖
    utils/logger.py
    db/
      database.py            # sqlite 连接、schema 初始化、首启种子
      schema.sql
    pipeline/
      fetch.py               # 抓取启用的源(httpx, UA, 重试);源 use_proxy=true 时走 http_proxy
      parse.py               # 解析 m3u/txt -> entries;提取 EPG(url-tvg/x-tvg-url)、tvg-logo
      normalize.py           # 模板+别名归一频道名(正则)
      dedup.py               # URL 去重
      check_http.py          # HTTP 可达 + 广告/占位过滤(ENDLIST 短循环、广告关键字)
      check_ffprobe.py       # ffprobe 播放确认 + 分辨率 + 下载速率采样 + 延迟
      filter_sort.py         # min_resolution/min_speed 阈值过滤;sort_by 多维排序;urls_limit 截断
      output.py              # 写 full.m3u / compact.m3u / iptv.txt(含 EPG 头、台标、$ 说明)
      runner.py              # 编排全流程,发进度/日志事件,写 SQLite + 落盘,历史合并,源自动停用
    scheduler/scheduler.py   # APScheduler: interval 或 time 模式,启动即跑,时区
    services/
      source_service.py      # 源/别名/模板 CRUD
      run_service.py         # 当前跑批状态 + 环形日志缓冲 + SSE 事件流 + 单跑批锁
      channel_service.py     # 频道结果查询
      report_service.py      # 统计聚合、历史
    routes/
      sources.py aliases.py templates.py tasks.py channels.py reports.py playlist.py
  frontend/                  # 仿 Frostcast
    src/{App,api,types,icons}.tsx
    src/index.css            # 照搬 Frostcast visionOS 毛玻璃 + 深浅主题变量
    src/components/{SourcesPanel,AliasPanel,TemplatePanel,TaskPanel,ChannelsPanel,ReportPanel,PlayerOverlay}.tsx
  Dockerfile
  docker-compose.yml
  start_dev.sh               # 一键启动: bun 构建前端 + uv 建 venv 装依赖 + run_dev.py
  output/                    # 生成的 m3u/txt(卷挂载)
  data/                      # sqlite(卷挂载)
```

现有 `iptv_cn.py` 的算法(去重、http_check、ffprobe_test、m3u/txt 输出格式、分组排序)迁入对应 `pipeline/*` 模块,保留并增强。

## 4. SQLite Schema

- `sources(id, name, url, type[m3u|txt], enabled, use_proxy, sort, note, fail_count, last_ok_at)`
  首启种子现有 5 个源(iptv-org-cn、guovin-gd result m3u/txt、yang gather/migu)。
  `use_proxy`:该源抓取时是否走全局代理(`fetch.http_proxy`),默认 false。
- `aliases(id, canonical, pattern, is_regex, enabled)`
  频道名归一:`pattern` 命中 -> 规范为 `canonical`。种子常见 CCTV/卫视别名。
- `templates(id, canonical, group_title, logo, sort, enabled)`
  想要的频道菜单 + 分组/台标/排序。可为空(空=不限制,收录全部)。
- `runs(id, started_at, finished_at, status[running|done|failed], stats_json)`
- `channels(id, run_id, name, group_title, url, logo, tvg_id, tvg_name, source, status, detail, resolution, speed, delay)`
  当前对外播放列表 = 最新 done run 的 channels。

生成的 m3u/txt 同时落盘到 `output/`,公开端点直接发文件(快,免查库)。

## 5. 数据流(runner.run)

```
cron/手动触发 -> 取单跑批锁 -> 新建 runs(status=running):
  1 fetch(启用的源)          # httpx, 全局/源级 UA, 重试;单源失败不中断
  2 parse                    # m3u/txt -> entries;顺带收集 EPG 地址、tvg-logo
  3 normalize                # 用 aliases 归一频道名;用 templates 匹配/分组(未匹配可选保留)
  4 dedup                    # URL 去重
  5 check_http               # 可达筛选 + 广告/占位过滤
  6 check_ffprobe            # 播放确认 + 分辨率 + 速率 + 延迟
  7 filter_sort              # 阈值过滤 -> sort_by 排序 -> 每频道 urls_limit 截断
  8 历史合并                 # 并入上次 done run 中本次缺失/变空频道的可用源
  9 output                   # 写 channels 表 + full.m3u/compact.m3u/iptv.txt(EPG头+台标+$说明)
  10 源自动停用              # 本次 0 命中/全失败的源 fail_count++,超阈值置 enabled=0
  -> runs(status=done, stats_json)
每步 emit 日志行 + 阶段进度 -> run_service 环形缓冲 -> SSE 推前端
异常 -> runs(status=failed),日志留存,释放锁
```

单跑批锁:同一时刻只允许一个 run(手动与定时互斥)。长任务在后台线程池执行,不阻塞 FastAPI 事件循环(沿用现有 ThreadPoolExecutor 做并发检测)。

## 6. HTTP 接口

公开(直出播放地址,发 `output/` 生成文件):
- `GET /full.m3u`      每频道全部通过源
- `GET /compact.m3u`   每频道前 urls_limit 个最佳源
- `GET /iptv.txt`      TVBox/DIYP 格式

API(`/api` 前缀):
- 源:      `GET/POST/PUT/DELETE /api/sources`
- 别名:    `GET/POST/PUT/DELETE /api/aliases`
- 模板:    `GET/POST/PUT/DELETE /api/templates`
- 任务:    `POST /api/tasks/run`(触发) · `GET /api/tasks/status` · `GET /api/tasks/logs`(SSE) · `GET/PUT /api/tasks/schedule`
- 频道:    `GET /api/channels?run=latest`
- 报告:    `GET /api/reports`(分组统计/清晰度分布/源健康度/历史跑批)

### 单端口托管(前后端同端口,照搬 Frostcast)

后端一个 uvicorn 进程同时服务 API、公开 m3u、前端静态页,**无独立前端 server**。`app.py` 的 `create_app()`:

1. 先 `include_router` 注册所有 API(`/api/*`)与公开文件路由(`/full.m3u`/`/compact.m3u`/`/iptv.txt`)——FastAPI 按注册顺序匹配,真实路由先命中。
2. `app.mount("/static", StaticFiles(...))` 挂载构建产物静态资源目录(`frontend/dist/static`)。
3. **最后**注册 catch-all `GET /{full_path:path}`(SPA fallback):
   - `full_path` 以 `api/` 开头 -> 404(交回真实 API,避免误吞)
   - 路径穿越防护(`..`、绝对路径、`\`、realpath 越界 -> 403)
   - 命中 `dist/` 下真实文件 -> `FileResponse`
   - 否则返回 `index.html`(前端路由自处理)
4. 静态目录可用 `FRONTEND` 环境变量覆盖,默认 `../frontend/dist`。

因公开 m3u 与 `/api` 路由先于 catch-all 注册,不会被 SPA fallback 吞掉。

dev 与 prod 都是单端口:`start_dev.sh` 用 `bun run build:dev -- --watch` 持续出 `frontend/dist`,后端 `run_dev.py`(reload)托管该目录;不起 rsbuild dev server,无跨端口代理。

## 7. 前端

顶部 brand + tools(分段控件切页 + Sun/Moon 主题开关),下方按 tab 渲染面板。

- SourcesPanel  — 源表格/卡片增删改、启禁开关、走代理开关(use_proxy)、显示 fail_count/last_ok
- AliasPanel    — 别名规则增删改(canonical / pattern / 正则开关)
- TemplatePanel — 频道模板菜单(canonical / 分组 / 台标 / 排序)
- TaskPanel     — 立即运行按钮 + SSE 实时日志 + 阶段进度条 + 调度设置(interval/time、时区、启动即跑)
- ChannelsPanel — 频道网格(名称/分组/分辨率/速率/状态),行内 mpegts.js `PlayerOverlay` 试播;顶部展示 3 个订阅地址(full/compact/txt)可复制
- ReportPanel   — 统计卡片:分组数、清晰度分布、源健康度、历史跑批

视觉系统照搬 Frostcast:

- visionOS 毛玻璃,CSS 变量驱动,`--accent:#E8735A`,`--blur:blur(40px) saturate(180%)`
- 深浅主题: `:root` + `:root[data-theme="light"]` 两套变量,主题存 localStorage,`.3s` 过渡,`documentElement[data-theme]` 切换
- 响应式: `clamp()` 流式尺寸 + `@media(max-width:560px)` 移动端布局 + `env(safe-area-inset-*)` + 触摸目标 ≥44px + `prefers-reduced-motion` 降级
- 背景色雾 `body::before` 径向渐变、卡片 hover 上浮、toast 反馈、PlayerOverlay 全屏/横屏播放 — 复用 Frostcast 组件

## 8. 配置(config.yaml + 环境变量覆盖)

```yaml
environment: production
server:
  port: 5180
schedule:
  update_mode: interval        # interval | time
  update_interval: 12          # 小时(interval 模式)
  update_times: []             # ["04:00"](time 模式)
  update_startup: true         # 启动即跑一次
  time_zone: Asia/Shanghai
fetch:
  user_agent: ""               # 空=内置默认
  request_timeout: 10
  retries: 2
  http_proxy: ""               # 全局代理地址(如 http://127.0.0.1:7890),空=不用;仅 use_proxy=true 的源生效
check:
  http_timeout: 6
  http_workers: 70
  ffprobe_enabled: true
  ffprobe_timeout: 10
  ffprobe_workers: 25
filter:
  urls_limit: 5
  min_resolution: 1280x720
  min_speed: 0.5               # M/s
  sort_by: resolution,speed    # resolution|speed|delay 逗号分隔
  open_filter_ad: true
  open_history: true
output:
  dir: ./output
  open_epg: true
  logo_url: ""                 # 台标库地址,空=仅用订阅源自带
  open_url_info: false         # m3u 频道名后 $ 说明(分辨率/来源)
logging:
  level: INFO
  log_dir: logs
db:
  path: ./data/iptv.db
```

源/别名/模板不在 yaml,存 SQLite(Web 可编,首启种子)。

## 9. 借鉴 Guovin 的特性映射

| 特性 | 落点 |
|---|---|
| 模板 + 频道别名(正则归一) | `templates`/`aliases` 表 + `pipeline/normalize.py` |
| 每频道 urls_limit | `filter.urls_limit` + `filter_sort.py` |
| 测速(速率/延迟/分辨率)+ sort_by | `check_ffprobe.py` + `filter.sort_by` |
| 广告/占位过滤 | `check_http.py`(ENDLIST 短循环、广告关键字) |
| 阈值过滤 min_resolution/min_speed | `filter_sort.py` |
| 源自动停用 | `runner.py` + `sources.fail_count/enabled` |
| 历史结果合并 | `runner.py` 合并上次 done run |
| EPG(url-tvg/x-tvg-url)+ 台标 | `parse.py` 提取 + `output.py` 写入 |
| 调度增强(interval/time、启动即跑、时区) | `scheduler/scheduler.py` |

## 10. Docker

多阶段:
1. `node` 阶段 — 装 frontend 依赖,`rsbuild build` 出 `frontend/dist`
2. `python:3.13-slim` 阶段 — `apt-get install ffmpeg`,装 requirements,拷 backend + dist,`run_prod.py` uvicorn 启动

`docker-compose.yml`:暴露单端口(5180),挂载 `./config.yaml`、`./data`(sqlite)、`./output`(m3u) 卷。

### 开发启动(start_dev.sh,仿 Frostcast)

```bash
./start_dev.sh [PORT]   # 默认 5180
```
流程:
1. 检查 `bun` / `uv` 存在
2. `cd frontend && bun install && bun run build:dev`,再 `bun run build:dev -- --watch &` 后台监听
3. `cd backend`,无 config.yaml 则从 example 拷贝
4. 无 `.venv` 则 `uv venv`,`uv pip install -r requirements.txt`
5. `python run_dev.py`(uvicorn reload)后台启动;后端 SPA fallback 服务 `frontend/dist`
6. `trap` 捕获 Ctrl+C,`kill` 前后端进程

## 11. 错误处理 / 测试

- 抓取单源失败不中断整批(现有行为),记日志,累加 fail_count
- 跑批异常 -> runs.status=failed,日志留存,释放单跑批锁
- ffprobe 缺失 -> 若 ffprobe_enabled 但二进制不存在,记警告并降级为仅 HTTP 检测
- pytest 覆盖 parse/normalize/dedup/filter_sort/output 纯函数 + 路由(httpx TestClient),仿 Frostcast 测试布局
```
