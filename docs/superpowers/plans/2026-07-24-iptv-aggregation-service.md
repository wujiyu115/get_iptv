# IPTV 聚合服务 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把单文件脚本 `iptv_cn.py` 改造成一个带 Web 配置界面、两阶段死链检测、定时抓取、SQLite 存储、单端口/单镜像部署的可长期运行 IPTV 聚合服务。

**Architecture:** FastAPI 单进程同端口托管 API + 公开 m3u/txt + React SPA（照搬 Frostcast 的 `create_app()` 工厂 + catch-all SPA fallback）。抓取管线拆成 `pipeline/*` 纯函数 + 有副作用的 `fetch/check_*/runner`，由 `runner.run()` 编排并通过环形缓冲 + SSE 推实时日志。源/别名/模板存 SQLite（Web 可编），跑批结果落 SQLite + `output/` 文件。APScheduler 按 interval/time 定时触发，单跑批锁保证互斥。

**Tech Stack:** Python 3.13 · FastAPI · uvicorn · httpx · APScheduler · PyYAML · sqlite3(stdlib) · ffprobe(subprocess) · React 18 · TypeScript · rsbuild · axios · mpegts.js · uv · bun · Docker(多阶段)。

## Global Constraints

- Python 版本下限：3.13。前端 React 18 + TypeScript 5。
- 后端只用 `sqlite3` 标准库，不引入 ORM。
- 单端口托管：一个 uvicorn 进程服务 `/api/*`、`/full.m3u` `/compact.m3u` `/iptv.txt`、SPA 静态页。默认端口 `5180`。
- 路由注册顺序：先 `/api/*` 与公开文件路由，最后注册 catch-all `GET /{full_path:path}`（SPA fallback）。`api/` 前缀在 catch-all 里返回 404，路径穿越（`..`/绝对路径/`\`/realpath 越界）返回 403。
- 配置优先级：环境变量 > `config.yaml` > 硬编码默认。`config.yaml` 路径可用 `CONFIG_FILE` 覆盖；静态目录用 `FRONTEND` 覆盖，默认 `../frontend/dist`。
- 源/别名/模板存 SQLite，不进 yaml。首启种子：5 个源 + 常见 CCTV/卫视别名。
- 单跑批锁：手动与定时互斥，同一时刻只允许一个 run。长任务在后台线程执行，不阻塞事件循环；检测并发沿用 `ThreadPoolExecutor`。
- TLS：抓取与检测统一使用不校验证书的 httpx client（`verify=False`），修正原脚本 fetch/check 不一致问题。
- 前端 axios `baseURL: '/api'`。视觉照搬 Frostcast：`--accent:#E8735A`、`--blur:blur(40px) saturate(180%)`、`:root` + `:root[data-theme="light"]` 两套变量、主题存 localStorage、`documentElement[data-theme]` 切换。
- 依赖工具：`uv`（Python venv/装依赖）、`bun`（前端依赖/构建）。开发用 `bun run build:dev -- --watch` 出 `frontend/dist`，后端托管，不起独立前端 server。
- DRY、YAGNI、TDD、frequent commits。每个 pipeline 纯函数先写失败测试再实现。
- 明确排除（不实现）：RTMP 推流/转码/nginx、回放、组播/酒店源、location/isp 过滤、public_domain 重写、GUI、performance_mode。

---

## File Structure

**新建目录树**（`get_iptv/` 下）：

```
backend/
  app.py                    # create_app: FastAPI, CORS, 挂路由, 挂 static, SPA fallback, 起 scheduler
  run_dev.py                # uvicorn reload
  run_prod.py               # uvicorn prod
  requirements.txt
  config.yaml.example       # 配置模板（start_dev 自动拷成 config.yaml）
  config/__init__.py
  config/config_loader.py   # yaml + dotted get + 环境变量覆盖
  utils/__init__.py
  utils/logger.py           # 命名 logger
  db/__init__.py
  db/schema.sql             # 建表 DDL
  db/database.py            # 连接、init_db、首启种子
  db/seed.py                # 种子数据常量（5源 + 别名）
  pipeline/__init__.py
  pipeline/models.py        # Entry / Channel dataclass（管线统一数据结构）
  pipeline/parse.py         # 纯函数：m3u+txt -> entries，EPG 提取
  pipeline/normalize.py     # 纯函数：alias 归一 + template 分组
  pipeline/dedup.py         # 纯函数：URL 去重
  pipeline/filter_sort.py   # 纯函数：阈值过滤 + sort_by 排序 + urls_limit 截断
  pipeline/output.py        # 纯函数：entries -> full.m3u / compact.m3u / iptv.txt 文本
  pipeline/fetch.py         # 副作用：httpx 抓源
  pipeline/check_http.py    # 副作用：HTTP 可达 + 广告/ENDLIST 过滤（线程池）
  pipeline/check_ffprobe.py # 副作用：ffprobe 播放确认 + 分辨率 + 速率 + 延迟（线程池）
  pipeline/runner.py        # 编排全流程，发事件，写库+落盘，历史合并，源自动停用
  scheduler/__init__.py
  scheduler/scheduler.py    # APScheduler：interval/time、启动即跑、时区
  services/__init__.py
  services/source_service.py    # 源/别名/模板 CRUD
  services/run_service.py       # 跑批状态 + 环形日志缓冲 + SSE + 单跑批锁
  services/channel_service.py   # 频道结果查询
  services/report_service.py    # 统计聚合/历史
  routes/__init__.py
  routes/sources.py routes/aliases.py routes/templates.py
  routes/tasks.py routes/channels.py routes/reports.py routes/playlist.py
  tests/                    # pytest；纯函数 + 路由(TestClient)
    test_parse.py test_normalize.py test_dedup.py test_filter_sort.py
    test_output.py test_database.py test_runner.py test_routes.py test_app.py
frontend/
  package.json rsbuild.config.ts tsconfig.json bun.lock(生成)
  src/index.tsx src/index.html src/index.css
  src/App.tsx src/api.ts src/types.ts src/icons.tsx
  src/components/{SourcesPanel,AliasPanel,TemplatePanel,TaskPanel,ChannelsPanel,ReportPanel,PlayerOverlay}.tsx
Dockerfile
docker-compose.yml
.dockerignore
start_dev.sh
output/  data/            # 运行时卷（可 .gitignore）
```

`iptv_cn.py` 的算法迁入对应模块并增强：`parse_m3u`→`parse.py`（新增 txt 解析、EPG 头提取）；URL 去重→`dedup.py`；`http_check`→`check_http.py`（新增广告/ENDLIST 过滤）；`ffprobe_test`→`check_ffprobe.py`（新增速率/延迟）；三个 writer→`output.py`；`group_sort_key`/`GROUP_ORDER`→保留在 output/filter_sort。原脚本保留不动，作为算法参考。

---

## Task 1: 后端脚手架（配置 + 日志 + 依赖）

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/config.yaml.example`
- Create: `backend/config/__init__.py`（空）
- Create: `backend/config/config_loader.py`
- Create: `backend/utils/__init__.py`（空）
- Create: `backend/utils/logger.py`
- Create: `backend/pipeline/__init__.py` `backend/db/__init__.py` `backend/services/__init__.py` `backend/routes/__init__.py` `backend/scheduler/__init__.py`（均空）
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `config.config_loader.config`（单例，`config.get("server.port", 5180)` dotted 访问）；`utils.logger.logger`（`logging.Logger`，name=`iptv`）。

- [ ] **Step 1: 写失败测试** — `backend/tests/test_config.py`

```python
import os, importlib

def test_dotted_get_and_default(tmp_path, monkeypatch):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("server:\n  port: 5180\nfilter:\n  urls_limit: 5\n", encoding="utf-8")
    monkeypatch.setenv("CONFIG_FILE", str(cfg))
    import config.config_loader as cl
    importlib.reload(cl)
    assert cl.config.get("server.port") == 5180
    assert cl.config.get("filter.urls_limit") == 5
    assert cl.config.get("missing.key", "fallback") == "fallback"

def test_missing_file_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("CONFIG_FILE", str(tmp_path / "nope.yaml"))
    import config.config_loader as cl
    importlib.reload(cl)
    assert cl.config.get("server.port", 5180) == 5180
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_config.py -v`
Expected: FAIL（`ModuleNotFoundError: config.config_loader`）

- [ ] **Step 3: 写 `config/config_loader.py`**

```python
import os
import yaml

_here = os.path.dirname(os.path.abspath(__file__))
_default_path = os.path.join(_here, "..", "config.yaml")


class Config:
    def __init__(self):
        path = os.environ.get("CONFIG_FILE") or _default_path
        self._data = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}

    def get(self, key, default=None):
        cur = self._data
        for part in key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return default
        return cur


config = Config()
```

- [ ] **Step 4: 写 `utils/logger.py`**

```python
import logging
import os

os.makedirs(os.environ.get("LOG_DIR", "logs"), exist_ok=True)
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("iptv")
```

- [ ] **Step 5: 写 `requirements.txt`**

```
fastapi==0.115.4
uvicorn[standard]==0.32.0
pyyaml==6.0.2
httpx==0.27.2
apscheduler==3.10.4
pytest
```

- [ ] **Step 6: 写 `config.yaml.example`**（来自 spec §8，逐字）

```yaml
environment: production
server:
  port: 5180
schedule:
  update_mode: interval        # interval | time
  update_interval: 12
  update_times: []
  update_startup: true
  time_zone: Asia/Shanghai
fetch:
  user_agent: ""
  request_timeout: 10
  retries: 2
  http_proxy: ""
check:
  http_timeout: 6
  http_workers: 70
  ffprobe_enabled: true
  ffprobe_timeout: 10
  ffprobe_workers: 25
filter:
  urls_limit: 5
  min_resolution: 1280x720
  min_speed: 0.5
  sort_by: resolution,speed
  open_filter_ad: true
  open_history: true
output:
  dir: ./output
  open_epg: true
  logo_url: ""
  open_url_info: false
logging:
  level: INFO
  log_dir: logs
db:
  path: ./data/iptv.db
```

- [ ] **Step 7: 建空 `__init__.py`** — 在 `config/ utils/ pipeline/ db/ services/ routes/ scheduler/ tests/` 各建一个空 `__init__.py`（tests 也建，便于导入）。并建 `backend/tests/conftest.py`：

```python
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

- [ ] **Step 8: 跑测试确认通过**

Run: `cd backend && uv venv && uv pip install -r requirements.txt && uv run pytest tests/test_config.py -v`
Expected: PASS（2 passed）

- [ ] **Step 9: Commit**

```bash
git init 2>/dev/null; git add backend/ && git commit -m "feat: backend scaffolding — config loader, logger, deps"
```

---

## Task 2: SQLite schema + 连接 + 首启种子

**Files:**
- Create: `backend/db/schema.sql`
- Create: `backend/db/seed.py`
- Create: `backend/db/database.py`
- Test: `backend/tests/test_database.py`

**Interfaces:**
- Consumes: `config.config_loader.config`（`db.path`）。
- Produces:
  - `db.database.get_conn() -> sqlite3.Connection`（`row_factory=sqlite3.Row`，`PRAGMA foreign_keys=ON`）
  - `db.database.init_db(conn=None) -> None`（执行 schema.sql；若 `sources` 空则插入种子）
  - `db.database.db_path() -> str`（env `DB_PATH` > `config db.path` > `./data/iptv.db`，返回后自动 `makedirs`）
  - 表：`sources(id,name,url,type,enabled,use_proxy,sort,note,fail_count,last_ok_at)`、`aliases(id,canonical,pattern,is_regex,enabled)`、`templates(id,canonical,group_title,logo,sort,enabled)`、`runs(id,started_at,finished_at,status,stats_json)`、`channels(id,run_id,name,group_title,url,logo,tvg_id,tvg_name,source,status,detail,resolution,speed,delay)`

- [ ] **Step 1: 写失败测试** — `backend/tests/test_database.py`

```python
import importlib


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    import db.database as d
    importlib.reload(d)
    d.init_db()
    return d


def test_tables_created(tmp_path, monkeypatch):
    d = _fresh_db(tmp_path, monkeypatch)
    conn = d.get_conn()
    names = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"sources", "aliases", "templates", "runs", "channels"} <= names


def test_seed_sources_and_aliases(tmp_path, monkeypatch):
    d = _fresh_db(tmp_path, monkeypatch)
    conn = d.get_conn()
    assert conn.execute("SELECT COUNT(*) c FROM sources").fetchone()["c"] == 5
    assert conn.execute("SELECT COUNT(*) c FROM aliases").fetchone()["c"] > 0


def test_seed_idempotent(tmp_path, monkeypatch):
    d = _fresh_db(tmp_path, monkeypatch)
    d.init_db()  # second call must not duplicate
    conn = d.get_conn()
    assert conn.execute("SELECT COUNT(*) c FROM sources").fetchone()["c"] == 5
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_database.py -v`
Expected: FAIL（`ModuleNotFoundError: db.database`）

- [ ] **Step 3: 写 `db/schema.sql`**

```sql
CREATE TABLE IF NOT EXISTS sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  url TEXT NOT NULL,
  type TEXT NOT NULL CHECK(type IN ('m3u','txt')),
  enabled INTEGER NOT NULL DEFAULT 1,
  use_proxy INTEGER NOT NULL DEFAULT 0,
  sort INTEGER NOT NULL DEFAULT 0,
  note TEXT DEFAULT '',
  fail_count INTEGER NOT NULL DEFAULT 0,
  last_ok_at TEXT
);
CREATE TABLE IF NOT EXISTS aliases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical TEXT NOT NULL,
  pattern TEXT NOT NULL,
  is_regex INTEGER NOT NULL DEFAULT 0,
  enabled INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS templates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical TEXT NOT NULL,
  group_title TEXT DEFAULT '',
  logo TEXT DEFAULT '',
  sort INTEGER NOT NULL DEFAULT 0,
  enabled INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL CHECK(status IN ('running','done','failed')),
  stats_json TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS channels (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  group_title TEXT DEFAULT '',
  url TEXT NOT NULL,
  logo TEXT DEFAULT '',
  tvg_id TEXT DEFAULT '',
  tvg_name TEXT DEFAULT '',
  source TEXT DEFAULT '',
  status TEXT DEFAULT '',
  detail TEXT DEFAULT '',
  resolution INTEGER DEFAULT 0,
  speed REAL DEFAULT 0,
  delay REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_channels_run ON channels(run_id);
```

- [ ] **Step 4: 写 `db/seed.py`**（种子常量，来自 iptv_cn.py `SOURCES` + spec §4）

```python
# (name, url, type)
SEED_SOURCES = [
    ("iptv-org-cn", "https://iptv-org.github.io/iptv/countries/cn.m3u", "m3u"),
    ("guovin-gd-result-m3u",
     "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u", "m3u"),
    ("guovin-gd-result-txt",
     "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.txt", "txt"),
    ("yang-gather", "https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u", "m3u"),
    ("yang-migu", "https://raw.githubusercontent.com/YanG-1989/m3u/main/Migu.m3u", "m3u"),
]

# (canonical, pattern, is_regex)
SEED_ALIASES = [
    ("CCTV1", r"^CCTV[-\s]?1(\s|综合|$)", 1),
    ("CCTV2", r"^CCTV[-\s]?2(\s|财经|$)", 1),
    ("CCTV5", r"^CCTV[-\s]?5(\s|体育|$)", 1),
    ("CCTV5+", r"^CCTV[-\s]?5\+(\s|体育赛事|$)", 1),
    ("CCTV13", r"^CCTV[-\s]?13(\s|新闻|$)", 1),
    ("湖南卫视", r"湖南卫视", 0),
    ("浙江卫视", r"浙江卫视", 0),
    ("东方卫视", r"东方卫视", 0),
    ("江苏卫视", r"江苏卫视", 0),
    ("北京卫视", r"北京卫视", 0),
]
```

- [ ] **Step 5: 写 `db/database.py`**

```python
import os
import sqlite3

from config.config_loader import config
from db.seed import SEED_SOURCES, SEED_ALIASES

_here = os.path.dirname(os.path.abspath(__file__))
_schema = os.path.join(_here, "schema.sql")


def db_path() -> str:
    p = os.environ.get("DB_PATH") or config.get("db.path", "./data/iptv.db")
    p = os.path.abspath(p)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection = None) -> None:
    own = conn is None
    conn = conn or get_conn()
    with open(_schema, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    if conn.execute("SELECT COUNT(*) c FROM sources").fetchone()["c"] == 0:
        conn.executemany(
            "INSERT INTO sources(name,url,type) VALUES (?,?,?)", SEED_SOURCES)
        conn.executemany(
            "INSERT INTO aliases(canonical,pattern,is_regex) VALUES (?,?,?)",
            SEED_ALIASES)
        conn.commit()
    if own:
        conn.commit()
        conn.close()
```

- [ ] **Step 6: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_database.py -v`
Expected: PASS（3 passed）

- [ ] **Step 7: Commit**

```bash
git add backend/db/ backend/tests/test_database.py && git commit -m "feat: sqlite schema, connection, first-run seed"
```

---

## Task 3: pipeline/models.py + parse.py（m3u+txt 解析 + EPG）

**Files:**
- Create: `backend/pipeline/models.py`
- Create: `backend/pipeline/parse.py`
- Test: `backend/tests/test_parse.py`

**Interfaces:**
- Produces:
  - `models.Entry`（dataclass：`name:str, url:str, logo:str="", group:str="", tvg_id:str="", tvg_name:str="", source:str="", status:str="", detail:str="", resolution:int=0, speed:float=0.0, delay:float=0.0`）
  - `parse.parse_m3u(text:str, source:str="") -> list[Entry]`
  - `parse.parse_txt(text:str, source:str="") -> list[Entry]`（TVBox `名称,URL` + `分组,#genre#` 格式）
  - `parse.parse(text:str, kind:str, source:str="") -> list[Entry]`（kind ∈ `m3u|txt` 分派）
  - `parse.extract_epg(text:str) -> list[str]`（`#EXTM3U` 头里的 `url-tvg=` / `x-tvg-url=`，逗号/分号拆分）
  - `SKIP_NAMES = ["温馨提示","免费订阅","维护","使用说明","Github","更新时间"]`（含则丢弃）
- Consumes（later）: dedup/normalize/check 都以 `list[Entry]` 流转。

- [ ] **Step 1: 写失败测试** — `backend/tests/test_parse.py`

```python
from pipeline.parse import parse_m3u, parse_txt, extract_epg, parse

M3U = '''#EXTM3U url-tvg="http://epg.a/x.xml,http://epg.b/y.xml"
#EXTINF:-1 tvg-id="cctv1" tvg-name="CCTV1" tvg-logo="http://l/1.png" group-title="央视",CCTV1 综合
http://a/1.m3u8
#EXTINF:-1 group-title="测试",温馨提示
http://a/skip.m3u8
#EXTINF:-1 group-title="卫视",湖南卫视
http://a/2.m3u8
'''

TXT = '''央视,#genre#
CCTV1,http://a/1.m3u8
CCTV2,http://a/2.m3u8
卫视,#genre#
湖南卫视,http://a/3.m3u8
'''


def test_parse_m3u_fields():
    es = parse_m3u(M3U, source="s1")
    assert len(es) == 2  # 温馨提示 被 SKIP_NAMES 丢弃
    e = es[0]
    assert e.name == "CCTV1 综合" and e.url == "http://a/1.m3u8"
    assert e.tvg_id == "cctv1" and e.logo == "http://l/1.png"
    assert e.group == "央视" and e.source == "s1"


def test_extract_epg():
    assert extract_epg(M3U) == ["http://epg.a/x.xml", "http://epg.b/y.xml"]


def test_parse_txt_genre():
    es = parse_txt(TXT, source="s2")
    assert len(es) == 3
    assert es[0].name == "CCTV1" and es[0].group == "央视"
    assert es[2].name == "湖南卫视" and es[2].group == "卫视"


def test_parse_dispatch():
    assert len(parse(M3U, "m3u")) == 2
    assert len(parse(TXT, "txt")) == 3
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_parse.py -v`
Expected: FAIL（`ModuleNotFoundError: pipeline.parse`）

- [ ] **Step 3: 写 `pipeline/models.py`**

```python
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
```

- [ ] **Step 4: 写 `pipeline/parse.py`**（迁移 iptv_cn.py `parse_m3u`，新增 txt/EPG）

```python
import re

from pipeline.models import Entry

SKIP_NAMES = ["温馨提示", "免费订阅", "维护", "使用说明", "Github", "更新时间"]
_URL_PREFIX = ("http://", "https://", "rtmp://", "rtsp://", "udp://")


def _skip(name: str) -> bool:
    return any(s in name for s in SKIP_NAMES)


def extract_epg(text: str) -> list[str]:
    urls: list[str] = []
    for line in text.splitlines():
        if not line.startswith("#EXTM3U"):
            continue
        for m in re.finditer(r'(?:url-tvg|x-tvg-url)="([^"]*)"', line):
            for u in re.split(r"[;,]", m.group(1)):
                u = u.strip()
                if u:
                    urls.append(u)
    return urls


def parse_m3u(text: str, source: str = "") -> list[Entry]:
    entries: list[Entry] = []
    cur: dict | None = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#EXTINF"):
            name_m = re.search(r",(.+)$", line)
            cur = {
                "name": (name_m.group(1).strip() if name_m else ""),
                "logo": _attr(line, "tvg-logo"),
                "group": _attr(line, "group-title"),
                "tvg_id": _attr(line, "tvg-id"),
                "tvg_name": _attr(line, "tvg-name"),
            }
        elif line.startswith(_URL_PREFIX) and cur is not None:
            if cur["name"] and not _skip(cur["name"]):
                entries.append(Entry(url=line, source=source, **cur))
            cur = None
    return entries


def parse_txt(text: str, source: str = "") -> list[Entry]:
    entries: list[Entry] = []
    group = ""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.endswith("#genre#"):
            group = line.split(",")[0].strip()
            continue
        if "," in line:
            name, url = line.split(",", 1)
            name, url = name.strip(), url.strip()
            if name and url.startswith(_URL_PREFIX) and not _skip(name):
                entries.append(Entry(name=name, url=url, group=group, source=source))
    return entries


def parse(text: str, kind: str, source: str = "") -> list[Entry]:
    return parse_txt(text, source) if kind == "txt" else parse_m3u(text, source)


def _attr(line: str, key: str) -> str:
    m = re.search(key + r'="([^"]*)"', line)
    return m.group(1) if m else ""
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_parse.py -v`
Expected: PASS（4 passed）

- [ ] **Step 6: Commit**

```bash
git add backend/pipeline/models.py backend/pipeline/parse.py backend/tests/test_parse.py && git commit -m "feat: pipeline models + m3u/txt parser with EPG extraction"
```

---

## Task 4: pipeline/normalize.py（别名归一 + 模板分组）

**Files:**
- Create: `backend/pipeline/normalize.py`
- Test: `backend/tests/test_normalize.py`

**Interfaces:**
- Consumes: `list[Entry]`（Task 3）。别名/模板以简单 dict 传入（解耦 DB）：
  - alias 项：`{"canonical":str,"pattern":str,"is_regex":bool}`
  - template 项：`{"canonical":str,"group_title":str,"logo":str,"sort":int}`
- Produces:
  - `normalize.apply_aliases(entries, aliases) -> list[Entry]`（命中 pattern -> `entry.name = canonical`；regex 用 `re.search`，非 regex 用子串包含；第一个命中的 alias 生效）
  - `normalize.apply_templates(entries, templates, keep_unmatched=True) -> list[Entry]`（name==canonical 时覆盖 `group_title`/`logo`（logo 仅在 entry 无 logo 时填），并打 `_tmpl_sort`；templates 为空 -> 全保留不改；`keep_unmatched=False` 时丢弃未匹配项）
- Produces later: `filter_sort`/`output` 消费归一后的 entries。

- [ ] **Step 1: 写失败测试** — `backend/tests/test_normalize.py`

```python
from pipeline.models import Entry
from pipeline.normalize import apply_aliases, apply_templates


def test_alias_regex_and_substring():
    es = [Entry(name="CCTV-1 综合", url="u1"), Entry(name="湖南卫视HD", url="u2")]
    aliases = [
        {"canonical": "CCTV1", "pattern": r"^CCTV[-\s]?1(\s|综合|$)", "is_regex": True},
        {"canonical": "湖南卫视", "pattern": "湖南卫视", "is_regex": False},
    ]
    out = apply_aliases(es, aliases)
    assert out[0].name == "CCTV1"
    assert out[1].name == "湖南卫视"


def test_template_sets_group_and_keeps_unmatched():
    es = [Entry(name="CCTV1", url="u1"), Entry(name="未知台", url="u2")]
    tmpls = [{"canonical": "CCTV1", "group_title": "央视", "logo": "L", "sort": 1}]
    out = apply_templates(es, tmpls, keep_unmatched=True)
    assert out[0].group == "央视" and out[0].logo == "L"
    assert len(out) == 2  # 未匹配保留


def test_template_drop_unmatched():
    es = [Entry(name="CCTV1", url="u1"), Entry(name="未知台", url="u2")]
    tmpls = [{"canonical": "CCTV1", "group_title": "央视", "logo": "", "sort": 1}]
    out = apply_templates(es, tmpls, keep_unmatched=False)
    assert [e.name for e in out] == ["CCTV1"]


def test_empty_templates_keep_all():
    es = [Entry(name="X", url="u")]
    assert len(apply_templates(es, [], keep_unmatched=True)) == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_normalize.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 写 `pipeline/normalize.py`**

```python
import re

from pipeline.models import Entry


def apply_aliases(entries: list[Entry], aliases: list[dict]) -> list[Entry]:
    for e in entries:
        for a in aliases:
            pat, canon = a["pattern"], a["canonical"]
            hit = (re.search(pat, e.name) if a.get("is_regex") else pat in e.name)
            if hit:
                e.name = canon
                break
    return entries


def apply_templates(entries: list[Entry], templates: list[dict],
                    keep_unmatched: bool = True) -> list[Entry]:
    if not templates:
        return entries
    by_canon = {t["canonical"]: t for t in templates}
    out: list[Entry] = []
    for e in entries:
        t = by_canon.get(e.name)
        if t:
            if t.get("group_title"):
                e.group = t["group_title"]
            if t.get("logo") and not e.logo:
                e.logo = t["logo"]
            setattr(e, "_tmpl_sort", t.get("sort", 0))
            out.append(e)
        elif keep_unmatched:
            setattr(e, "_tmpl_sort", 10_000)
            out.append(e)
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_normalize.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/normalize.py backend/tests/test_normalize.py && git commit -m "feat: normalize — alias canonicalization + template grouping"
```

---

## Task 5: pipeline/dedup.py（URL 去重）

**Files:**
- Create: `backend/pipeline/dedup.py`
- Test: `backend/tests/test_dedup.py`

**Interfaces:**
- Consumes: `list[Entry]`。
- Produces: `dedup.dedup(entries) -> list[Entry]`（按 `url.strip().lower()` 去重，首现优先，保持顺序）。

- [ ] **Step 1: 写失败测试** — `backend/tests/test_dedup.py`

```python
from pipeline.models import Entry
from pipeline.dedup import dedup


def test_dedup_keeps_first_preserves_order():
    es = [
        Entry(name="A", url="http://X/1"),
        Entry(name="B", url="HTTP://x/1"),  # 大小写等价 -> 去掉
        Entry(name="C", url="http://X/2 "),  # 末尾空格
        Entry(name="D", url="http://x/2"),   # 与 C strip+lower 后等价 -> 去掉
    ]
    out = dedup(es)
    assert [e.name for e in out] == ["A", "C"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_dedup.py -v`
Expected: FAIL

- [ ] **Step 3: 写 `pipeline/dedup.py`**（迁移 iptv_cn.py `step2_parse_dedup`）

```python
from pipeline.models import Entry


def dedup(entries: list[Entry]) -> list[Entry]:
    seen: set[str] = set()
    out: list[Entry] = []
    for e in entries:
        key = e.url.strip().lower()
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_dedup.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/dedup.py backend/tests/test_dedup.py && git commit -m "feat: url dedup"
```

---

## Task 6: pipeline/filter_sort.py（阈值过滤 + 排序 + urls_limit）

**Files:**
- Create: `backend/pipeline/filter_sort.py`
- Test: `backend/tests/test_filter_sort.py`

**Interfaces:**
- Consumes: `list[Entry]`（已带 `resolution:int(高度)`、`speed:float`、`delay:float`）。
- Produces:
  - `filter_sort.parse_resolution(s:str) -> int`（`"1280x720" -> 720`，取高度；非法 -> 0）
  - `filter_sort.apply(entries, *, min_resolution="", min_speed=0.0, sort_by="resolution,speed", urls_limit=0) -> list[Entry]`
    - 阈值：`resolution >= min_height`（min_resolution 空则不限）；`speed >= min_speed`（0 则不限，但 speed==0 视为未测速，不因此淘汰）
    - 排序：先按 `group` 的稳定分组，再在每个频道内按 `sort_by`（`resolution` desc / `speed` desc / `delay` asc 逗号优先级）
    - `urls_limit>0`：每个 `name` 只保留前 N 个（截断在排序后按 name 分桶做）

- [ ] **Step 1: 写失败测试** — `backend/tests/test_filter_sort.py`

```python
from pipeline.models import Entry
from pipeline.filter_sort import apply, parse_resolution


def test_parse_resolution():
    assert parse_resolution("1920x1080") == 1080
    assert parse_resolution("1280x720") == 720
    assert parse_resolution("bad") == 0


def test_min_resolution_filter():
    es = [Entry(name="A", url="u1", resolution=1080),
          Entry(name="A", url="u2", resolution=480)]
    out = apply(es, min_resolution="1280x720")
    assert [e.url for e in out] == ["u1"]


def test_sort_and_urls_limit_per_channel():
    es = [
        Entry(name="A", url="lo", resolution=480, speed=2.0),
        Entry(name="A", url="hi", resolution=1080, speed=1.0),
        Entry(name="A", url="mid", resolution=720, speed=9.0),
    ]
    out = apply(es, sort_by="resolution,speed", urls_limit=2)
    a = [e.url for e in out if e.name == "A"]
    assert a == ["hi", "mid"]  # 分辨率优先，截断到 2


def test_speed_zero_not_dropped_when_min_speed_set():
    es = [Entry(name="A", url="u", resolution=1080, speed=0.0)]
    out = apply(es, min_speed=0.5)
    assert len(out) == 1  # speed==0 视为未测速，保留
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_filter_sort.py -v`
Expected: FAIL

- [ ] **Step 3: 写 `pipeline/filter_sort.py`**

```python
import re
from collections import OrderedDict

from pipeline.models import Entry


def parse_resolution(s: str) -> int:
    m = re.match(r"\s*\d+\s*[xX]\s*(\d+)", s or "")
    return int(m.group(1)) if m else 0


def _sort_key(sort_by: str):
    fields = [f.strip() for f in sort_by.split(",") if f.strip()]

    def key(e: Entry):
        parts = []
        for f in fields:
            if f == "resolution":
                parts.append(-e.resolution)
            elif f == "speed":
                parts.append(-e.speed)
            elif f == "delay":
                parts.append(e.delay if e.delay > 0 else float("inf"))
        return tuple(parts)

    return key


def apply(entries: list[Entry], *, min_resolution: str = "", min_speed: float = 0.0,
          sort_by: str = "resolution,speed", urls_limit: int = 0) -> list[Entry]:
    min_h = parse_resolution(min_resolution)
    kept = []
    for e in entries:
        if min_h and e.resolution and e.resolution < min_h:
            continue
        if min_speed and e.speed and e.speed < min_speed:
            continue
        kept.append(e)

    kept.sort(key=_sort_key(sort_by))

    if urls_limit and urls_limit > 0:
        counts: dict[str, int] = {}
        limited = []
        for e in kept:
            c = counts.get(e.name, 0)
            if c < urls_limit:
                counts[e.name] = c + 1
                limited.append(e)
        kept = limited

    # regroup so same channel's urls stay adjacent, groups in first-seen order
    buckets: "OrderedDict[str, list[Entry]]" = OrderedDict()
    for e in kept:
        buckets.setdefault(e.name, []).append(e)
    out: list[Entry] = []
    for v in buckets.values():
        out.extend(v)
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_filter_sort.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/filter_sort.py backend/tests/test_filter_sort.py && git commit -m "feat: threshold filter + multi-key sort + per-channel urls_limit"
```

---

## Task 7: pipeline/output.py（生成 full/compact m3u + iptv.txt 文本）

**Files:**
- Create: `backend/pipeline/output.py`
- Test: `backend/tests/test_output.py`

**Interfaces:**
- Consumes: `list[Entry]`（已过滤排序）。
- Produces:
  - `output.build_full_m3u(entries, *, epg_urls=None, open_url_info=False) -> str`（每条通过源都写；`#EXTM3U` 头含 `url-tvg`（若 open_epg 且有 epg_urls）；`open_url_info` 时频道名后加 ` $分辨率|来源`）
  - `output.build_compact_m3u(entries, *, epg_urls=None, open_url_info=False) -> str`（每频道仅第 1 条）
  - `output.build_txt(entries) -> str`（TVBox `分组,#genre#` + `名称,URL`，compact 口径每频道 1 条）
  - `output.write_all(entries, out_dir, *, epg_urls=None, open_epg=True, open_url_info=False) -> dict`（写 `full.m3u`/`compact.m3u`/`iptv.txt`，返回文件名->路径）

- [ ] **Step 1: 写失败测试** — `backend/tests/test_output.py`

```python
from pipeline.models import Entry
from pipeline.output import build_full_m3u, build_compact_m3u, build_txt, write_all


def _sample():
    return [
        Entry(name="CCTV1", url="u1", group="央视", logo="L1", resolution=1080),
        Entry(name="CCTV1", url="u2", group="央视", logo="L1", resolution=720),
        Entry(name="湖南卫视", url="u3", group="卫视", resolution=1080),
    ]


def test_full_m3u_has_all_urls_and_epg():
    m = build_full_m3u(_sample(), epg_urls=["http://epg/x.xml"])
    assert m.startswith("#EXTM3U")
    assert 'url-tvg="http://epg/x.xml"' in m
    assert m.count("#EXTINF") == 3
    assert "u1" in m and "u2" in m and "u3" in m


def test_compact_one_per_channel():
    m = build_compact_m3u(_sample())
    assert m.count("#EXTINF") == 2  # CCTV1 只留一条 + 湖南卫视
    assert "u1" in m and "u2" not in m


def test_txt_genre_format():
    t = build_txt(_sample())
    assert "央视,#genre#" in t
    assert "CCTV1,u1" in t
    assert "湖南卫视,u3" in t


def test_write_all(tmp_path):
    files = write_all(_sample(), str(tmp_path), epg_urls=None)
    assert (tmp_path / "full.m3u").exists()
    assert (tmp_path / "compact.m3u").exists()
    assert (tmp_path / "iptv.txt").exists()
    assert set(files) == {"full.m3u", "compact.m3u", "iptv.txt"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_output.py -v`
Expected: FAIL

- [ ] **Step 3: 写 `pipeline/output.py`**（迁移 iptv_cn.py 三个 writer）

```python
import os
from collections import OrderedDict

from pipeline.models import Entry


def _header(epg_urls) -> str:
    if epg_urls:
        return '#EXTM3U url-tvg="' + ",".join(epg_urls) + '"'
    return "#EXTM3U"


def _extinf(e: Entry, open_url_info: bool) -> str:
    name = e.name
    if open_url_info:
        info = []
        if e.resolution:
            info.append(f"{e.resolution}p")
        if e.source:
            info.append(e.source)
        if info:
            name = f"{name} ${'|'.join(info)}"
    group = e.group or "其他"
    return (f'#EXTINF:-1 tvg-id="{e.tvg_id}" tvg-name="{e.tvg_name or e.name}" '
            f'tvg-logo="{e.logo}" group-title="{group}",{name}')


def _compact(entries: list[Entry]) -> list[Entry]:
    seen: "OrderedDict[str, Entry]" = OrderedDict()
    for e in entries:
        if e.name not in seen:
            seen[e.name] = e
    return list(seen.values())


def build_full_m3u(entries, *, epg_urls=None, open_url_info=False) -> str:
    lines = [_header(epg_urls)]
    for e in entries:
        lines.append(_extinf(e, open_url_info))
        lines.append(e.url)
    return "\n".join(lines) + "\n"


def build_compact_m3u(entries, *, epg_urls=None, open_url_info=False) -> str:
    lines = [_header(epg_urls)]
    for e in _compact(entries):
        lines.append(_extinf(e, open_url_info))
        lines.append(e.url)
    return "\n".join(lines) + "\n"


def build_txt(entries) -> str:
    lines: list[str] = []
    cur_group = None
    for e in _compact(entries):
        g = e.group or "其他"
        if g != cur_group:
            if lines:
                lines.append("")
            lines.append(f"{g},#genre#")
            cur_group = g
        lines.append(f"{e.name},{e.url}")
    return "\n".join(lines) + "\n"


def write_all(entries, out_dir, *, epg_urls=None, open_epg=True,
              open_url_info=False) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    epg = epg_urls if open_epg else None
    files = {
        "full.m3u": build_full_m3u(entries, epg_urls=epg, open_url_info=open_url_info),
        "compact.m3u": build_compact_m3u(entries, epg_urls=epg, open_url_info=open_url_info),
        "iptv.txt": build_txt(entries),
    }
    paths = {}
    for name, content in files.items():
        p = os.path.join(out_dir, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        paths[name] = p
    return paths
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_output.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/output.py backend/tests/test_output.py && git commit -m "feat: output writers — full/compact m3u + tvbox txt with EPG header"
```

---

## Task 8: pipeline/fetch.py（httpx 抓源 + 代理 + 重试）

**Files:**
- Create: `backend/pipeline/fetch.py`
- Test: `backend/tests/test_fetch.py`

**Interfaces:**
- Consumes: source dict `{"name","url","type","use_proxy"}`。
- Produces:
  - `fetch.DEFAULT_UA`（iPhone UA，来自 iptv_cn.py）
  - `fetch.fetch_one(source, *, user_agent="", timeout=10, retries=2, http_proxy="") -> tuple[dict, str|None]`（返回 `(source, text)`；失败返回 `(source, None)`；`use_proxy` 且 `http_proxy` 非空时走代理；`verify=False`；小于 50 字节视为失败）
  - `fetch.fetch_all(sources, *, user_agent="", timeout=10, retries=2, http_proxy="", on_log=None) -> list[tuple[dict,str]]`（单源失败不中断，`on_log(msg)` 回调发日志；只返回成功的）

- [ ] **Step 1: 写失败测试** — `backend/tests/test_fetch.py`（用 monkeypatch 假 httpx，不打真网络）

```python
import pipeline.fetch as fetch


class _Resp:
    def __init__(self, text): self.text = text
    def raise_for_status(self): pass


class _Client:
    def __init__(self, *a, **k): pass
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def get(self, url, headers=None):
        if "bad" in url:
            raise RuntimeError("boom")
        return _Resp("#EXTM3U\n#EXTINF:-1,A\nhttp://a/1\n")


def test_fetch_one_ok(monkeypatch):
    monkeypatch.setattr(fetch.httpx, "Client", _Client)
    src = {"name": "s", "url": "http://ok", "type": "m3u", "use_proxy": 0}
    s, text = fetch.fetch_one(src, retries=0)
    assert text and "#EXTM3U" in text


def test_fetch_one_fail_returns_none(monkeypatch):
    monkeypatch.setattr(fetch.httpx, "Client", _Client)
    src = {"name": "s", "url": "http://bad", "type": "m3u", "use_proxy": 0}
    s, text = fetch.fetch_one(src, retries=1)
    assert text is None


def test_fetch_all_skips_failures(monkeypatch):
    monkeypatch.setattr(fetch.httpx, "Client", _Client)
    srcs = [{"name": "ok", "url": "http://ok", "type": "m3u", "use_proxy": 0},
            {"name": "bad", "url": "http://bad", "type": "m3u", "use_proxy": 0}]
    out = fetch.fetch_all(srcs, retries=0)
    assert [s["name"] for s, _ in out] == ["ok"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_fetch.py -v`
Expected: FAIL

- [ ] **Step 3: 写 `pipeline/fetch.py`**

```python
import httpx

DEFAULT_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
              "AppleWebKit/605.1.15")


def fetch_one(source: dict, *, user_agent: str = "", timeout: int = 10,
              retries: int = 2, http_proxy: str = ""):
    ua = user_agent or DEFAULT_UA
    proxy = http_proxy if source.get("use_proxy") and http_proxy else None
    last_err = None
    for _ in range(retries + 1):
        try:
            with httpx.Client(timeout=timeout, verify=False, follow_redirects=True,
                              proxy=proxy) as client:
                r = client.get(source["url"], headers={"User-Agent": ua})
                r.raise_for_status()
                text = r.text
                if len(text) < 50:
                    last_err = "response too small"
                    continue
                return source, text
        except Exception as e:  # noqa: BLE001 - single source must not abort batch
            last_err = str(e)
    return source, None


def fetch_all(sources, *, user_agent: str = "", timeout: int = 10, retries: int = 2,
              http_proxy: str = "", on_log=None):
    out = []
    for src in sources:
        s, text = fetch_one(src, user_agent=user_agent, timeout=timeout,
                            retries=retries, http_proxy=http_proxy)
        if text is not None:
            out.append((s, text))
            if on_log:
                on_log(f"fetch ok: {s['name']} ({len(text)} bytes)")
        elif on_log:
            on_log(f"fetch FAIL: {s['name']}")
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_fetch.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/fetch.py backend/tests/test_fetch.py && git commit -m "feat: httpx source fetcher with proxy + retries"
```

---

## Task 9: pipeline/check_http.py（HTTP 可达 + 广告/ENDLIST 过滤）

**Files:**
- Create: `backend/pipeline/check_http.py`
- Test: `backend/tests/test_check_http.py`

**Interfaces:**
- Consumes: `list[Entry]`。
- Produces:
  - `check_http.AD_KEYWORDS`（列表：广告/占位关键字，如 `"广告"`, `"advertisement"`, `"占位"`）
  - `check_http.classify_body(code:int, content_type:str, body:bytes) -> str`（纯函数，返回 `"ok"|"dead"|"ad"`；含 `#EXT-X-ENDLIST` 且极短 -> `"ad"`（占位短循环）；命中广告关键字 -> `"ad"`；200 且（含 `#extm3u/#extinf` 或 content-type 含 video 或 body>200）-> `"ok"`；否则 `"dead"`）
  - `check_http.check_all(entries, *, timeout=6, workers=70, open_filter_ad=True, on_log=None) -> list[Entry]`（`ThreadPoolExecutor` 并发；非 http(s) 前缀（rtmp/rtsp/udp）直接保留；`ok` 保留；`ad` 在 open_filter_ad 时丢弃）

- [ ] **Step 1: 写失败测试** — `backend/tests/test_check_http.py`（`classify_body` 纯函数直测，避免网络）

```python
from pipeline.check_http import classify_body


def test_ok_m3u_body():
    assert classify_body(200, "application/x-mpegurl",
                          b"#EXTM3U\n#EXTINF:-1,A\nhttp://a/1\n") == "ok"


def test_ok_video_content_type():
    assert classify_body(200, "video/mp2t", b"\x00" * 500) == "ok"


def test_dead_non_200():
    assert classify_body(404, "text/html", b"not found") == "dead"


def test_ad_endlist_short_loop():
    body = b"#EXTM3U\n#EXT-X-ENDLIST\n"  # 极短 + ENDLIST = 占位
    assert classify_body(200, "application/x-mpegurl", body) == "ad"


def test_ad_keyword():
    assert classify_body(200, "text/plain", "这是广告占位".encode()) == "ad"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_check_http.py -v`
Expected: FAIL

- [ ] **Step 3: 写 `pipeline/check_http.py`**（迁移 iptv_cn.py `http_check` + 新增广告过滤）

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from pipeline.fetch import DEFAULT_UA
from pipeline.models import Entry

AD_KEYWORDS = ["广告", "占位", "advertisement", "sponsor"]
_HTTP = ("http://", "https://")


def classify_body(code: int, content_type: str, body: bytes) -> str:
    bs = body.decode("utf-8", errors="replace").lower()
    ct = (content_type or "").lower()
    if any(k.lower() in bs for k in AD_KEYWORDS):
        return "ad"
    if "#ext-x-endlist" in bs and len(body) < 300:
        return "ad"
    if code == 200 and ("#extm3u" in bs or "#extinf" in bs
                        or "video" in ct or len(body) > 200):
        return "ok"
    return "dead"


def _check_one(e: Entry, timeout: int):
    if not e.url.startswith(_HTTP):
        return e, "ok"  # rtmp/rtsp/udp bypass HTTP check
    try:
        with httpx.Client(timeout=timeout, verify=False, follow_redirects=True) as c:
            r = c.get(e.url, headers={"User-Agent": DEFAULT_UA})
            body = r.content[:8192]
            return e, classify_body(r.status_code,
                                    r.headers.get("content-type", ""), body)
    except Exception:  # noqa: BLE001
        return e, "dead"


def check_all(entries, *, timeout=6, workers=70, open_filter_ad=True, on_log=None):
    out = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_check_one, e, timeout) for e in entries]
        for fut in as_completed(futs):
            e, status = fut.result()
            if status == "ok":
                out.append(e)
            elif status == "ad" and not open_filter_ad:
                out.append(e)
    if on_log:
        on_log(f"http check: {len(out)}/{len(entries)} reachable")
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_check_http.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/check_http.py backend/tests/test_check_http.py && git commit -m "feat: http reachability check with ad/ENDLIST filtering"
```

---

## Task 10: pipeline/check_ffprobe.py（播放确认 + 分辨率 + 速率 + 延迟）

**Files:**
- Create: `backend/pipeline/check_ffprobe.py`
- Test: `backend/tests/test_check_ffprobe.py`

**Interfaces:**
- Consumes: `list[Entry]`。
- Produces:
  - `check_ffprobe.ffprobe_available() -> bool`（`shutil.which("ffprobe")`）
  - `check_ffprobe.parse_probe_json(out:str) -> tuple[str, int]`（纯函数：解析 ffprobe JSON，返回 `(detail, height)`；取第一个 video 流 `codec_name WxH`，height 为分辨率；无 video 但有 audio -> `("audio", 0)`；无流 -> `("no-streams", 0)`）
  - `check_ffprobe.build_cmd(url:str, timeout:int) -> list[str]`（纯函数：ffprobe 命令，含 `-show_entries stream=codec_type,codec_name,width,height -of json` + 采样 flag）
  - `check_ffprobe.check_all(entries, *, timeout=10, workers=25, enabled=True, on_log=None) -> list[Entry]`（`enabled=False` 或二进制缺失 -> 降级：原样返回、记警告；否则线程池跑，只保留 playable，填 `resolution/detail`，用 wall-clock 探测耗时填 `delay`(秒)，`speed` 由 probesize/耗时估算 M/s）

- [ ] **Step 1: 写失败测试** — `backend/tests/test_check_ffprobe.py`（纯函数直测）

```python
from pipeline.check_ffprobe import parse_probe_json, build_cmd


def test_parse_video_stream():
    j = '{"streams":[{"codec_type":"video","codec_name":"h264","width":1920,"height":1080}]}'
    detail, h = parse_probe_json(j)
    assert h == 1080 and "h264" in detail and "1920x1080" in detail


def test_parse_audio_only():
    j = '{"streams":[{"codec_type":"audio","codec_name":"aac"}]}'
    detail, h = parse_probe_json(j)
    assert detail == "audio" and h == 0


def test_parse_no_streams():
    detail, h = parse_probe_json('{"streams":[]}')
    assert detail == "no-streams" and h == 0


def test_build_cmd_has_json_and_url():
    cmd = build_cmd("http://a/1.m3u8", 10)
    assert cmd[0] == "ffprobe"
    assert "-of" in cmd and "json" in cmd
    assert cmd[-1] == "http://a/1.m3u8"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_check_ffprobe.py -v`
Expected: FAIL

- [ ] **Step 3: 写 `pipeline/check_ffprobe.py`**（迁移 iptv_cn.py `ffprobe_test` + 新增 speed/delay）

```python
import json
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from pipeline.models import Entry

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


def check_all(entries, *, timeout=10, workers=25, enabled=True, on_log=None):
    if not enabled or not ffprobe_available():
        if on_log:
            on_log("ffprobe disabled/missing — skipping playback confirmation")
        for e in entries:
            e.status = "unchecked"
        return entries
    out = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_probe_one, e, timeout) for e in entries]
        for fut in as_completed(futs):
            e, ok = fut.result()
            if ok:
                out.append(e)
    if on_log:
        on_log(f"ffprobe: {len(out)}/{len(entries)} playable")
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_check_ffprobe.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/check_ffprobe.py backend/tests/test_check_ffprobe.py && git commit -m "feat: ffprobe playback check with resolution/speed/delay + graceful degrade"
```

---

## Task 11: pipeline/runner.py（编排 + 历史合并 + 源自动停用 + 事件）

**Files:**
- Create: `backend/pipeline/runner.py`
- Test: `backend/tests/test_runner.py`

**Interfaces:**
- Consumes: 所有 pipeline 模块 + `db.database`。
- Produces:
  - `runner.merge_history(current:list[Entry], previous:list[Entry]) -> list[Entry]`（纯函数：previous 里有、current 里缺失的频道名，补回其可用源；current 优先）
  - `runner.RunContext`（`emit(msg:str, stage:str="")` 回调容器；默认 no-op）
  - `runner.run(*, on_event=None) -> int`（主编排，返回 run_id；步骤：取锁->建 running run->fetch->parse+epg->normalize(alias+template)->dedup->check_http->check_ffprobe->filter_sort->history merge->output(写库+落盘)->源自动停用->done；异常->failed 并释放锁）
  - `FAIL_DISABLE_THRESHOLD = 5`（`fail_count` 超阈值 `enabled=0`）
- 说明：DB 读写用 `db.get_conn()`；源自动停用：本次 0 命中/全失败的源 `fail_count++`，成功源 `fail_count=0` 且更新 `last_ok_at`。

- [ ] **Step 1: 写失败测试** — `backend/tests/test_runner.py`（测纯函数 merge_history + 源停用逻辑，主 run 用 monkeypatch 打桩 fetch/check）

```python
import importlib

from pipeline.models import Entry
from pipeline.runner import merge_history, FAIL_DISABLE_THRESHOLD


def test_merge_history_backfills_missing_channels():
    current = [Entry(name="CCTV1", url="new1")]
    previous = [Entry(name="CCTV1", url="old1"), Entry(name="CCTV2", url="old2")]
    out = merge_history(current, previous)
    names = {e.name for e in out}
    assert names == {"CCTV1", "CCTV2"}
    cctv1 = [e.url for e in out if e.name == "CCTV1"]
    assert "new1" in cctv1  # current 优先保留


def test_merge_history_no_previous():
    current = [Entry(name="A", url="u")]
    assert merge_history(current, []) == current


def test_run_end_to_end_stubbed(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("CONFIG_FILE", str(tmp_path / "cfg.yaml"))
    (tmp_path / "cfg.yaml").write_text(
        f"output:\n  dir: {tmp_path}/out\ncheck:\n  ffprobe_enabled: false\n",
        encoding="utf-8")
    import db.database as d
    importlib.reload(d)
    d.init_db()
    import pipeline.fetch as fetch
    import pipeline.runner as runner
    importlib.reload(fetch)
    importlib.reload(runner)

    def fake_fetch_all(sources, **k):
        return [({"name": "s", "type": "m3u"},
                 "#EXTM3U\n#EXTINF:-1 group-title=\"央视\",CCTV1\nhttp://a/1\n")]
    monkeypatch.setattr(runner.fetch, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(runner.check_http, "check_all", lambda es, **k: es)

    logs = []
    run_id = runner.run(on_event=lambda msg, stage="": logs.append(msg))
    conn = d.get_conn()
    row = conn.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()
    assert row["status"] == "done"
    assert conn.execute("SELECT COUNT(*) c FROM channels WHERE run_id=?",
                        (run_id,)).fetchone()["c"] >= 1
    assert (tmp_path / "out" / "full.m3u").exists()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_runner.py -v`
Expected: FAIL

- [ ] **Step 3: 写 `pipeline/runner.py`**

```python
import json
from datetime import datetime, timezone

from config.config_loader import config
from db import database
from pipeline import (check_ffprobe, check_http, dedup, fetch, filter_sort,
                      normalize, output, parse)
from pipeline.models import Entry

FAIL_DISABLE_THRESHOLD = 5


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def merge_history(current: list[Entry], previous: list[Entry]) -> list[Entry]:
    if not previous:
        return current
    have = {e.name for e in current}
    out = list(current)
    for e in previous:
        if e.name not in have:
            out.append(e)
    return out


def _load_prev_channels(conn) -> list[Entry]:
    row = conn.execute(
        "SELECT id FROM runs WHERE status='done' ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return []
    rows = conn.execute(
        "SELECT name,group_title,url,logo,tvg_id,tvg_name,source,resolution,speed,delay "
        "FROM channels WHERE run_id=?", (row["id"],)).fetchall()
    return [Entry(name=r["name"], url=r["url"], group=r["group_title"], logo=r["logo"],
                  tvg_id=r["tvg_id"], tvg_name=r["tvg_name"], source=r["source"],
                  resolution=r["resolution"], speed=r["speed"], delay=r["delay"])
            for r in rows]


def run(*, on_event=None) -> int:
    emit = on_event or (lambda msg, stage="": None)
    conn = database.get_conn()
    cur = conn.execute("INSERT INTO runs(started_at,status) VALUES (?, 'running')",
                       (_now(),))
    run_id = cur.lastrowid
    conn.commit()
    try:
        sources = [dict(r) for r in conn.execute(
            "SELECT * FROM sources WHERE enabled=1 ORDER BY sort, id").fetchall()]
        aliases = [dict(r) for r in conn.execute(
            "SELECT canonical,pattern,is_regex FROM aliases WHERE enabled=1").fetchall()]
        templates = [dict(r) for r in conn.execute(
            "SELECT canonical,group_title,logo,sort FROM templates WHERE enabled=1 "
            "ORDER BY sort").fetchall()]

        emit("stage: fetch", "fetch")
        fetched = fetch.fetch_all(
            sources, user_agent=config.get("fetch.user_agent", ""),
            timeout=config.get("fetch.request_timeout", 10),
            retries=config.get("fetch.retries", 2),
            http_proxy=config.get("fetch.http_proxy", ""),
            on_log=lambda m: emit(m, "fetch"))
        ok_names = {s["name"] for s, _ in fetched}

        emit("stage: parse", "parse")
        entries: list[Entry] = []
        epg_urls: list[str] = []
        for src, text in fetched:
            entries.extend(parse.parse(text, src["type"], source=src["name"]))
            epg_urls.extend(parse.extract_epg(text))
        epg_urls = list(dict.fromkeys(epg_urls))

        emit("stage: normalize", "normalize")
        entries = normalize.apply_aliases(entries, aliases)
        entries = normalize.apply_templates(entries, templates, keep_unmatched=True)

        emit("stage: dedup", "dedup")
        entries = dedup.dedup(entries)

        emit("stage: check_http", "check_http")
        entries = check_http.check_all(
            entries, timeout=config.get("check.http_timeout", 6),
            workers=config.get("check.http_workers", 70),
            open_filter_ad=config.get("filter.open_filter_ad", True),
            on_log=lambda m: emit(m, "check_http"))

        emit("stage: check_ffprobe", "check_ffprobe")
        entries = check_ffprobe.check_all(
            entries, timeout=config.get("check.ffprobe_timeout", 10),
            workers=config.get("check.ffprobe_workers", 25),
            enabled=config.get("check.ffprobe_enabled", True),
            on_log=lambda m: emit(m, "check_ffprobe"))

        emit("stage: filter_sort", "filter_sort")
        entries = filter_sort.apply(
            entries, min_resolution=config.get("filter.min_resolution", ""),
            min_speed=config.get("filter.min_speed", 0.0),
            sort_by=config.get("filter.sort_by", "resolution,speed"),
            urls_limit=config.get("filter.urls_limit", 0))

        if config.get("filter.open_history", True):
            emit("stage: history merge", "history")
            entries = merge_history(entries, _load_prev_channels(conn))

        emit("stage: output", "output")
        out_dir = config.get("output.dir", "./output")
        conn.executemany(
            "INSERT INTO channels(run_id,name,group_title,url,logo,tvg_id,tvg_name,"
            "source,status,detail,resolution,speed,delay) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(run_id, e.name, e.group, e.url, e.logo, e.tvg_id, e.tvg_name, e.source,
              e.status or "ok", e.detail, e.resolution, e.speed, e.delay)
             for e in entries])
        output.write_all(entries, out_dir, epg_urls=epg_urls,
                         open_epg=config.get("output.open_epg", True),
                         open_url_info=config.get("output.open_url_info", False))

        emit("stage: source auto-disable", "sources")
        present_sources = {e.source for e in entries}
        for src in sources:
            if src["name"] in ok_names and src["name"] in present_sources:
                conn.execute("UPDATE sources SET fail_count=0, last_ok_at=? WHERE id=?",
                            (_now(), src["id"]))
            else:
                fc = src["fail_count"] + 1
                enabled = 0 if fc >= FAIL_DISABLE_THRESHOLD else 1
                conn.execute("UPDATE sources SET fail_count=?, enabled=? WHERE id=?",
                            (fc, enabled, src["id"]))

        stats = {"channels": len(entries),
                 "groups": len({e.group for e in entries}),
                 "sources_ok": len(ok_names)}
        conn.execute("UPDATE runs SET status='done', finished_at=?, stats_json=? WHERE id=?",
                    (_now(), json.dumps(stats, ensure_ascii=False), run_id))
        conn.commit()
        emit(f"done: {stats}", "done")
        return run_id
    except Exception as e:  # noqa: BLE001
        conn.execute("UPDATE runs SET status='failed', finished_at=? WHERE id=?",
                    (_now(), run_id))
        conn.commit()
        emit(f"FAILED: {e}", "failed")
        raise
    finally:
        conn.close()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_runner.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/runner.py backend/tests/test_runner.py && git commit -m "feat: pipeline runner — orchestration, history merge, source auto-disable"
```

---

## Task 12: services 层（source/run/channel/report）

**Files:**
- Create: `backend/services/source_service.py`
- Create: `backend/services/run_service.py`
- Create: `backend/services/channel_service.py`
- Create: `backend/services/report_service.py`
- Test: `backend/tests/test_services.py`

**Interfaces:**
- `source_service`：`list_sources()/create_source(d)/update_source(id,d)/delete_source(id)`；`list_aliases()/create_alias(d)/update_alias(id,d)/delete_alias(id)`；`list_templates()/create_template(d)/update_template(id,d)/delete_template(id)`。均返回/接受 dict。
- `run_service`（模块级单例状态）：
  - `RingBuffer`（`maxlen=1000` 环形日志）
  - `state`：`{"status":"idle|running|done|failed","stage":"","run_id":None,"started_at":None}`
  - `try_acquire() -> bool` / `release()`（单跑批锁，`threading.Lock`）
  - `push_log(msg, stage="")`（写环形缓冲 + 更新 stage + 通知订阅者）
  - `subscribe() -> Queue` / `unsubscribe(q)`（SSE 用）
  - `start_run_async()`（若锁空闲，后台线程跑 `runner.run(on_event=push_log)`，忙则抛 `RuntimeError`）
  - `snapshot() -> dict`（当前 state + 最近 N 条日志）
- `channel_service`：`list_channels(run="latest") -> list[dict]`（latest = 最新 done run）。
- `report_service`：`report() -> dict`（分组计数、清晰度分布 1080p+/720p/480p/SD、源健康度(fail_count/last_ok/enabled)、历史跑批列表）。

- [ ] **Step 1: 写失败测试** — `backend/tests/test_services.py`

```python
import importlib


def _setup(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    import db.database as d
    importlib.reload(d)
    d.init_db()
    import services.source_service as ss
    import services.run_service as rs
    importlib.reload(ss); importlib.reload(rs)
    return ss, rs


def test_source_crud(tmp_path, monkeypatch):
    ss, _ = _setup(tmp_path, monkeypatch)
    n0 = len(ss.list_sources())
    sid = ss.create_source({"name": "x", "url": "http://x", "type": "m3u"})
    assert len(ss.list_sources()) == n0 + 1
    ss.update_source(sid, {"enabled": 0})
    assert [s for s in ss.list_sources() if s["id"] == sid][0]["enabled"] == 0
    ss.delete_source(sid)
    assert len(ss.list_sources()) == n0


def test_run_lock_mutex(tmp_path, monkeypatch):
    _, rs = _setup(tmp_path, monkeypatch)
    assert rs.try_acquire() is True
    assert rs.try_acquire() is False  # 已占用
    rs.release()
    assert rs.try_acquire() is True
    rs.release()


def test_ring_buffer_and_snapshot(tmp_path, monkeypatch):
    _, rs = _setup(tmp_path, monkeypatch)
    rs.push_log("hello", "fetch")
    snap = rs.snapshot()
    assert snap["stage"] == "fetch"
    assert any("hello" in x for x in snap["logs"])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_services.py -v`
Expected: FAIL

- [ ] **Step 3: 写 `services/source_service.py`**

```python
from db.database import get_conn

_SRC_FIELDS = ("name", "url", "type", "enabled", "use_proxy", "sort", "note")
_ALIAS_FIELDS = ("canonical", "pattern", "is_regex", "enabled")
_TMPL_FIELDS = ("canonical", "group_title", "logo", "sort", "enabled")


def _rows(sql, args=()):
    conn = get_conn()
    try:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def _insert(table, fields, d):
    cols = [f for f in fields if f in d]
    conn = get_conn()
    try:
        cur = conn.execute(
            f"INSERT INTO {table}({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            [d[c] for c in cols])
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _update(table, fields, _id, d):
    cols = [f for f in fields if f in d]
    if not cols:
        return
    conn = get_conn()
    try:
        conn.execute(f"UPDATE {table} SET {','.join(c + '=?' for c in cols)} WHERE id=?",
                    [d[c] for c in cols] + [_id])
        conn.commit()
    finally:
        conn.close()


def _delete(table, _id):
    conn = get_conn()
    try:
        conn.execute(f"DELETE FROM {table} WHERE id=?", (_id,))
        conn.commit()
    finally:
        conn.close()


def list_sources(): return _rows("SELECT * FROM sources ORDER BY sort, id")
def create_source(d): return _insert("sources", _SRC_FIELDS, d)
def update_source(i, d): _update("sources", _SRC_FIELDS, i, d)
def delete_source(i): _delete("sources", i)

def list_aliases(): return _rows("SELECT * FROM aliases ORDER BY id")
def create_alias(d): return _insert("aliases", _ALIAS_FIELDS, d)
def update_alias(i, d): _update("aliases", _ALIAS_FIELDS, i, d)
def delete_alias(i): _delete("aliases", i)

def list_templates(): return _rows("SELECT * FROM templates ORDER BY sort, id")
def create_template(d): return _insert("templates", _TMPL_FIELDS, d)
def update_template(i, d): _update("templates", _TMPL_FIELDS, i, d)
def delete_template(i): _delete("templates", i)
```

- [ ] **Step 4: 写 `services/run_service.py`**

```python
import threading
from collections import deque
from datetime import datetime, timezone
from queue import Queue

from pipeline import runner

_LOCK = threading.Lock()
_logs: deque = deque(maxlen=1000)
_subscribers: list[Queue] = []
_sub_lock = threading.Lock()

state = {"status": "idle", "stage": "", "run_id": None, "started_at": None}


def try_acquire() -> bool:
    return _LOCK.acquire(blocking=False)


def release() -> None:
    if _LOCK.locked():
        _LOCK.release()


def subscribe() -> Queue:
    q: Queue = Queue()
    with _sub_lock:
        _subscribers.append(q)
    return q


def unsubscribe(q: Queue) -> None:
    with _sub_lock:
        if q in _subscribers:
            _subscribers.remove(q)


def push_log(msg: str, stage: str = "") -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    _logs.append(line)
    if stage:
        state["stage"] = stage
    with _sub_lock:
        for q in list(_subscribers):
            q.put(line)


def snapshot() -> dict:
    return {**state, "logs": list(_logs)[-200:]}


def _run_thread():
    state.update(status="running", started_at=datetime.now(timezone.utc).isoformat())
    try:
        rid = runner.run(on_event=push_log)
        state.update(status="done", run_id=rid)
    except Exception:  # noqa: BLE001
        state["status"] = "failed"
    finally:
        release()


def start_run_async() -> None:
    if not try_acquire():
        raise RuntimeError("a run is already in progress")
    _logs.clear()
    threading.Thread(target=_run_thread, daemon=True).start()
```

- [ ] **Step 5: 写 `services/channel_service.py`**

```python
from db.database import get_conn


def _latest_done_run_id(conn):
    row = conn.execute(
        "SELECT id FROM runs WHERE status='done' ORDER BY id DESC LIMIT 1").fetchone()
    return row["id"] if row else None


def list_channels(run: str = "latest") -> list[dict]:
    conn = get_conn()
    try:
        rid = _latest_done_run_id(conn) if run == "latest" else int(run)
        if rid is None:
            return []
        return [dict(r) for r in conn.execute(
            "SELECT * FROM channels WHERE run_id=? ORDER BY group_title, name", (rid,))]
    finally:
        conn.close()
```

- [ ] **Step 6: 写 `services/report_service.py`**

```python
from collections import Counter

from db.database import get_conn


def report() -> dict:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id FROM runs WHERE status='done' ORDER BY id DESC LIMIT 1").fetchone()
        channels = []
        if row:
            channels = [dict(r) for r in conn.execute(
                "SELECT group_title,resolution FROM channels WHERE run_id=?", (row["id"],))]
        groups = Counter(c["group_title"] or "其他" for c in channels)
        buckets = Counter()
        for c in channels:
            h = c["resolution"]
            buckets["1080p+" if h >= 1080 else "720p" if h >= 720
                    else "480p" if h >= 480 else "SD"] += 1
        sources = [dict(r) for r in conn.execute(
            "SELECT name,enabled,fail_count,last_ok_at FROM sources ORDER BY sort, id")]
        runs = [dict(r) for r in conn.execute(
            "SELECT id,started_at,finished_at,status,stats_json FROM runs "
            "ORDER BY id DESC LIMIT 20")]
        return {"groups": dict(groups), "resolution": dict(buckets),
                "sources": sources, "runs": runs}
    finally:
        conn.close()
```

- [ ] **Step 7: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_services.py -v`
Expected: PASS（3 passed）

- [ ] **Step 8: Commit**

```bash
git add backend/services/ backend/tests/test_services.py && git commit -m "feat: service layer — sources CRUD, run lock+SSE buffer, channels, reports"
```

---

## Task 13: routes — sources / aliases / templates / channels / reports

**Files:**
- Create: `backend/routes/sources.py`
- Create: `backend/routes/aliases.py`
- Create: `backend/routes/templates.py`
- Create: `backend/routes/channels.py`
- Create: `backend/routes/reports.py`
- Test: 合并进 `backend/tests/test_routes.py`（Task 16 汇总）

**Interfaces:**
- 每个文件导出 `router = APIRouter(prefix="/api")`。
- Consumes: services 层。
- Produces（供 `app.py` include）：
  - `sources.router`：`GET/POST /api/sources`、`PUT/DELETE /api/sources/{id}`
  - `aliases.router`：`GET/POST /api/aliases`、`PUT/DELETE /api/aliases/{id}`
  - `templates.router`：`GET/POST /api/templates`、`PUT/DELETE /api/templates/{id}`
  - `channels.router`：`GET /api/channels?run=latest`
  - `reports.router`：`GET /api/reports`

- [ ] **Step 1: 写 `routes/sources.py`**

```python
from fastapi import APIRouter
from pydantic import BaseModel

from services import source_service as svc

router = APIRouter(prefix="/api")


class SourceIn(BaseModel):
    name: str | None = None
    url: str | None = None
    type: str | None = None
    enabled: int | None = None
    use_proxy: int | None = None
    sort: int | None = None
    note: str | None = None


@router.get("/sources")
def list_sources():
    return svc.list_sources()


@router.post("/sources")
def create_source(body: SourceIn):
    return {"id": svc.create_source(body.model_dump(exclude_none=True))}


@router.put("/sources/{sid}")
def update_source(sid: int, body: SourceIn):
    svc.update_source(sid, body.model_dump(exclude_none=True))
    return {"ok": True}


@router.delete("/sources/{sid}")
def delete_source(sid: int):
    svc.delete_source(sid)
    return {"ok": True}
```

- [ ] **Step 2: 写 `routes/aliases.py`**（同构，字段 canonical/pattern/is_regex/enabled）

```python
from fastapi import APIRouter
from pydantic import BaseModel

from services import source_service as svc

router = APIRouter(prefix="/api")


class AliasIn(BaseModel):
    canonical: str | None = None
    pattern: str | None = None
    is_regex: int | None = None
    enabled: int | None = None


@router.get("/aliases")
def list_aliases():
    return svc.list_aliases()


@router.post("/aliases")
def create_alias(body: AliasIn):
    return {"id": svc.create_alias(body.model_dump(exclude_none=True))}


@router.put("/aliases/{aid}")
def update_alias(aid: int, body: AliasIn):
    svc.update_alias(aid, body.model_dump(exclude_none=True))
    return {"ok": True}


@router.delete("/aliases/{aid}")
def delete_alias(aid: int):
    svc.delete_alias(aid)
    return {"ok": True}
```

- [ ] **Step 3: 写 `routes/templates.py`**（同构，字段 canonical/group_title/logo/sort/enabled）

```python
from fastapi import APIRouter
from pydantic import BaseModel

from services import source_service as svc

router = APIRouter(prefix="/api")


class TemplateIn(BaseModel):
    canonical: str | None = None
    group_title: str | None = None
    logo: str | None = None
    sort: int | None = None
    enabled: int | None = None


@router.get("/templates")
def list_templates():
    return svc.list_templates()


@router.post("/templates")
def create_template(body: TemplateIn):
    return {"id": svc.create_template(body.model_dump(exclude_none=True))}


@router.put("/templates/{tid}")
def update_template(tid: int, body: TemplateIn):
    svc.update_template(tid, body.model_dump(exclude_none=True))
    return {"ok": True}


@router.delete("/templates/{tid}")
def delete_template(tid: int):
    svc.delete_template(tid)
    return {"ok": True}
```

- [ ] **Step 4: 写 `routes/channels.py`**

```python
from fastapi import APIRouter, Query

from services import channel_service as svc

router = APIRouter(prefix="/api")


@router.get("/channels")
def list_channels(run: str = Query("latest")):
    return svc.list_channels(run)
```

- [ ] **Step 5: 写 `routes/reports.py`**

```python
from fastapi import APIRouter

from services import report_service as svc

router = APIRouter(prefix="/api")


@router.get("/reports")
def reports():
    return svc.report()
```

- [ ] **Step 6: Commit**

```bash
git add backend/routes/sources.py backend/routes/aliases.py backend/routes/templates.py backend/routes/channels.py backend/routes/reports.py && git commit -m "feat: CRUD + query routes (sources/aliases/templates/channels/reports)"
```

（这些路由在 Task 16 的 `test_routes.py` 中统一用 TestClient 验证。）

---

## Task 14: routes/tasks.py（触发 / 状态 / SSE 日志 / 调度）

**Files:**
- Create: `backend/routes/tasks.py`
- Test: 合并进 Task 16 `test_routes.py`

**Interfaces:**
- Consumes: `run_service`、`scheduler.scheduler`（Task 17 提供 `get_schedule()/set_schedule(d)`；本任务先定义占位读取 config）。
- Produces: `tasks.router = APIRouter(prefix="/api")`
  - `POST /api/tasks/run` -> `start_run_async()`；忙则 409
  - `GET /api/tasks/status` -> `run_service.snapshot()`
  - `GET /api/tasks/logs` -> SSE（`text/event-stream`，先补发快照日志，再实时推 subscribe 队列）
  - `GET /api/tasks/schedule` / `PUT /api/tasks/schedule` -> 读/写调度（委托 scheduler 模块）

- [ ] **Step 1: 写 `routes/tasks.py`**

```python
import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services import run_service

router = APIRouter(prefix="/api")


class ScheduleIn(BaseModel):
    update_mode: str | None = None
    update_interval: int | None = None
    update_times: list[str] | None = None
    update_startup: bool | None = None
    time_zone: str | None = None


@router.post("/tasks/run")
def trigger():
    try:
        run_service.start_run_async()
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"ok": True}


@router.get("/tasks/status")
def status():
    return run_service.snapshot()


@router.get("/tasks/logs")
async def logs():
    q = run_service.subscribe()
    snap = run_service.snapshot()

    async def gen():
        try:
            for line in snap["logs"]:
                yield f"data: {line}\n\n"
            while True:
                try:
                    line = q.get_nowait()
                    yield f"data: {line}\n\n"
                except Exception:  # noqa: BLE001
                    await asyncio.sleep(0.5)
                    yield ": keepalive\n\n"
        finally:
            run_service.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/tasks/schedule")
def get_schedule():
    from scheduler import scheduler
    return scheduler.get_schedule()


@router.put("/tasks/schedule")
def set_schedule(body: ScheduleIn):
    from scheduler import scheduler
    scheduler.set_schedule(body.model_dump(exclude_none=True))
    return {"ok": True}
```

- [ ] **Step 2: Commit**

```bash
git add backend/routes/tasks.py && git commit -m "feat: task routes — trigger, status, SSE logs, schedule read/write"
```

（SSE 与触发的验证放在 Task 16。scheduler 的 `get_schedule/set_schedule` 在 Task 17 实现。）

---

## Task 15: routes/playlist.py（公开 m3u/txt 直发文件）

**Files:**
- Create: `backend/routes/playlist.py`
- Test: 合并进 Task 16

**Interfaces:**
- Consumes: `config.output.dir`。
- Produces: `playlist.router = APIRouter()`（**无 `/api` 前缀**）
  - `GET /full.m3u` `GET /compact.m3u` `GET /iptv.txt`：直接 `FileResponse` 发 `output/` 下文件；不存在返回 404。m3u 用 `audio/x-mpegurl`，txt 用 `text/plain; charset=utf-8`。

- [ ] **Step 1: 写 `routes/playlist.py`**

```python
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config.config_loader import config

router = APIRouter()

_MEDIA = {"full.m3u": "audio/x-mpegurl", "compact.m3u": "audio/x-mpegurl",
          "iptv.txt": "text/plain; charset=utf-8"}


def _serve(name: str):
    out_dir = os.environ.get("OUTPUT_DIR") or config.get("output.dir", "./output")
    path = os.path.join(out_dir, name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="not generated yet")
    return FileResponse(path, media_type=_MEDIA[name])


@router.get("/full.m3u")
def full(): return _serve("full.m3u")


@router.get("/compact.m3u")
def compact(): return _serve("compact.m3u")


@router.get("/iptv.txt")
def txt(): return _serve("iptv.txt")
```

- [ ] **Step 2: Commit**

```bash
git add backend/routes/playlist.py && git commit -m "feat: public playlist routes serving generated m3u/txt files"
```

---

## Task 16: app.py（create_app + SPA fallback） + run_dev/run_prod + 路由集成测试

**Files:**
- Create: `backend/app.py`
- Create: `backend/run_dev.py`
- Create: `backend/run_prod.py`
- Test: `backend/tests/test_routes.py`, `backend/tests/test_app.py`

**Interfaces:**
- Consumes: 所有 `routes/*.router`、`db.database.init_db`、`scheduler.scheduler.start`（Task 17）。
- Produces: `app.create_app() -> FastAPI`；`app.app = create_app()`。
- 路由注册顺序（关键）：先 API routers（sources/aliases/templates/tasks/channels/reports）+ playlist，再 `mount("/static")`，最后 catch-all SPA。

- [ ] **Step 1: 写失败测试** — `backend/tests/test_routes.py`

```python
import importlib


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("FRONTEND", str(tmp_path / "nodist"))  # 无前端，跳过 catch-all
    import db.database as d
    importlib.reload(d)
    d.init_db()
    import app as appmod
    importlib.reload(appmod)
    from fastapi.testclient import TestClient
    return TestClient(appmod.app)


def test_sources_crud_via_api(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert len(c.get("/api/sources").json()) == 5
    rid = c.post("/api/sources", json={"name": "x", "url": "http://x", "type": "m3u"}).json()["id"]
    assert len(c.get("/api/sources").json()) == 6
    c.put(f"/api/sources/{rid}", json={"enabled": 0})
    c.delete(f"/api/sources/{rid}")
    assert len(c.get("/api/sources").json()) == 5


def test_task_status_idle(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.get("/api/tasks/status").json()["status"] in ("idle", "running", "done")


def test_playlist_404_before_generation(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.get("/full.m3u").status_code == 404


def test_reports_shape(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    body = c.get("/api/reports").json()
    assert set(body) == {"groups", "resolution", "sources", "runs"}
```

`backend/tests/test_app.py`（SPA fallback + 路径穿越）：

```python
import importlib


def _client_with_frontend(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    (dist / "static").mkdir(parents=True)
    (dist / "index.html").write_text("<html>spa</html>", encoding="utf-8")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("FRONTEND", str(dist))
    import db.database as d
    importlib.reload(d)
    d.init_db()
    import app as appmod
    importlib.reload(appmod)
    from fastapi.testclient import TestClient
    return TestClient(appmod.app)


def test_spa_fallback_serves_index(tmp_path, monkeypatch):
    c = _client_with_frontend(tmp_path, monkeypatch)
    r = c.get("/some/frontend/route")
    assert r.status_code == 200 and "spa" in r.text


def test_unknown_api_under_catchall_is_404(tmp_path, monkeypatch):
    c = _client_with_frontend(tmp_path, monkeypatch)
    assert c.get("/api/does-not-exist").status_code == 404


def test_path_traversal_blocked(tmp_path, monkeypatch):
    c = _client_with_frontend(tmp_path, monkeypatch)
    assert c.get("/../secret").status_code in (403, 404)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_routes.py tests/test_app.py -v`
Expected: FAIL（`ModuleNotFoundError: app`）

- [ ] **Step 3: 写 `app.py`**（照搬 Frostcast 工厂 + fallback）

```python
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from db.database import init_db
from utils.logger import logger

current_dir = os.path.dirname(os.path.abspath(__file__))


def create_app() -> FastAPI:
    app = FastAPI(title="IPTV 聚合服务", version="1.0.0")
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"])

    init_db()

    from routes.sources import router as sources_router
    from routes.aliases import router as aliases_router
    from routes.templates import router as templates_router
    from routes.tasks import router as tasks_router
    from routes.channels import router as channels_router
    from routes.reports import router as reports_router
    from routes.playlist import router as playlist_router
    for r in (sources_router, aliases_router, templates_router, tasks_router,
              channels_router, reports_router, playlist_router):
        app.include_router(r)

    try:
        from scheduler import scheduler
        scheduler.start()
    except Exception as e:  # noqa: BLE001
        logger.warning("scheduler not started: %s", e)

    static_folder = os.getenv("FRONTEND") or os.path.join(current_dir, "../frontend/dist")
    if os.path.exists(static_folder):
        static_assets = os.path.join(static_folder, "static")
        if os.path.exists(static_assets):
            app.mount("/static", StaticFiles(directory=static_assets), name="static")

        @app.get("/{full_path:path}")
        async def serve_spa(request: Request, full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse({"message": "Not Found"}, status_code=404)
            if ".." in full_path or full_path.startswith("/") or "\\" in full_path:
                return JSONResponse({"message": "Access Denied"}, status_code=403)
            file_path = os.path.join(static_folder, full_path)
            real = os.path.realpath(file_path)
            root = os.path.realpath(static_folder)
            if real != root and not real.startswith(root + os.sep):
                return JSONResponse({"message": "Access Denied"}, status_code=403)
            if os.path.isfile(file_path):
                return FileResponse(file_path)
            index_path = os.path.join(static_folder, "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path, media_type="text/html")
            return JSONResponse({"message": "Frontend not found"}, status_code=404)

    logger.info("IPTV app created")
    return app


app = create_app()
```

- [ ] **Step 4: 写 `run_dev.py` / `run_prod.py`**

`run_dev.py`:
```python
import argparse
import os

import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", type=int, default=None)
    parser.add_argument("--host", type=str, default=os.environ.get("HOST", "0.0.0.0"))
    args, _ = parser.parse_known_args()
    port = args.port or int(os.environ.get("PORT", "5180"))
    uvicorn.run("app:app", host=args.host, port=port, reload=True, log_level="info")
```

`run_prod.py`:
```python
import os

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5180"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, log_level="info")
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_routes.py tests/test_app.py -v`
Expected: PASS（4 + 3 passed）

- [ ] **Step 6: 全量回归**

Run: `cd backend && uv run pytest -v`
Expected: 全 PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app.py backend/run_dev.py backend/run_prod.py backend/tests/test_routes.py backend/tests/test_app.py && git commit -m "feat: create_app factory, SPA fallback, dev/prod runners + route integration tests"
```

---

## Task 17: scheduler/scheduler.py（APScheduler：interval/time + 启动即跑 + 时区）

**Files:**
- Create: `backend/scheduler/scheduler.py`
- Test: `backend/tests/test_scheduler.py`

**Interfaces:**
- Consumes: `config`（schedule.*）、`run_service.start_run_async`。
- Produces:
  - `scheduler.get_schedule() -> dict`（当前调度配置，从内存 override 或 config）
  - `scheduler.set_schedule(d:dict) -> None`（更新内存配置并重建 job）
  - `scheduler.start() -> None`（幂等；建 `BackgroundScheduler(timezone=...)`；interval 模式加 IntervalTrigger(hours)，time 模式对每个 HH:MM 加 CronTrigger；`update_startup` 为真则提交一次 `start_run_async`；用 try/except 吞掉锁忙）
  - `scheduler.shutdown() -> None`
- 任务函数 `_job()`：`try: run_service.start_run_async() except RuntimeError: pass`（跑批互斥，忙则跳过本次触发）。

- [ ] **Step 1: 写失败测试** — `backend/tests/test_scheduler.py`

```python
import importlib


def test_get_set_schedule(tmp_path, monkeypatch):
    monkeypatch.setenv("CONFIG_FILE", str(tmp_path / "c.yaml"))
    (tmp_path / "c.yaml").write_text(
        "schedule:\n  update_mode: interval\n  update_interval: 12\n"
        "  update_startup: false\n  time_zone: Asia/Shanghai\n", encoding="utf-8")
    import config.config_loader as cl
    import scheduler.scheduler as s
    importlib.reload(cl); importlib.reload(s)
    sched = s.get_schedule()
    assert sched["update_mode"] == "interval" and sched["update_interval"] == 12
    s.set_schedule({"update_interval": 6})
    assert s.get_schedule()["update_interval"] == 6


def test_start_builds_jobs_no_startup(tmp_path, monkeypatch):
    monkeypatch.setenv("CONFIG_FILE", str(tmp_path / "c.yaml"))
    (tmp_path / "c.yaml").write_text(
        "schedule:\n  update_mode: interval\n  update_interval: 3\n"
        "  update_startup: false\n  time_zone: UTC\n", encoding="utf-8")
    import config.config_loader as cl
    import scheduler.scheduler as s
    importlib.reload(cl); importlib.reload(s)
    s.start()
    assert s._scheduler is not None
    assert len(s._scheduler.get_jobs()) == 1
    s.shutdown()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_scheduler.py -v`
Expected: FAIL

- [ ] **Step 3: 写 `scheduler/scheduler.py`**

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config.config_loader import config
from services import run_service
from utils.logger import logger

_scheduler: BackgroundScheduler | None = None
_override: dict = {}


def get_schedule() -> dict:
    base = {
        "update_mode": config.get("schedule.update_mode", "interval"),
        "update_interval": config.get("schedule.update_interval", 12),
        "update_times": config.get("schedule.update_times", []),
        "update_startup": config.get("schedule.update_startup", True),
        "time_zone": config.get("schedule.time_zone", "Asia/Shanghai"),
    }
    base.update(_override)
    return base


def set_schedule(d: dict) -> None:
    _override.update(d)
    if _scheduler is not None:
        _rebuild_jobs()


def _job() -> None:
    try:
        run_service.start_run_async()
    except RuntimeError:
        logger.info("scheduled run skipped — a run is in progress")


def _rebuild_jobs() -> None:
    sched = get_schedule()
    _scheduler.remove_all_jobs()
    if sched["update_mode"] == "time":
        for hhmm in sched["update_times"]:
            hh, mm = hhmm.split(":")
            _scheduler.add_job(_job, CronTrigger(hour=int(hh), minute=int(mm),
                                                 timezone=sched["time_zone"]))
    else:
        _scheduler.add_job(_job, IntervalTrigger(hours=sched["update_interval"],
                                                 timezone=sched["time_zone"]))


def start() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    sched = get_schedule()
    _scheduler = BackgroundScheduler(timezone=sched["time_zone"])
    _rebuild_jobs()
    _scheduler.start()
    if sched["update_startup"]:
        try:
            run_service.start_run_async()
        except RuntimeError:
            pass


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_scheduler.py -v`
Expected: PASS

- [ ] **Step 5: 后端全量回归**

Run: `cd backend && uv run pytest -v`
Expected: 全 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/scheduler/ backend/tests/test_scheduler.py && git commit -m "feat: APScheduler — interval/time modes, startup run, timezone, run-on-schedule mutex"
```

---

## Task 18: 前端脚手架（rsbuild + 主题 CSS + api/types）

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/rsbuild.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/src/index.html`
- Create: `frontend/src/index.tsx`
- Create: `frontend/src/index.css`
- Create: `frontend/src/api.ts`
- Create: `frontend/src/types.ts`
- Create: `frontend/src/icons.tsx`

**Interfaces:**
- Produces: axios 单例（`baseURL:'/api'`）+ 全部 API 函数；TS 类型；主题 CSS 变量系统（照搬 Frostcast）。
- Consumes later: 各 Panel 组件 import `api.ts`/`types.ts`。

- [ ] **Step 1: 写 `package.json`**

```json
{
  "name": "iptv-frontend",
  "private": true,
  "version": "1.0.0",
  "scripts": {
    "dev": "rsbuild dev",
    "build": "rsbuild build",
    "build:dev": "NODE_ENV=development rsbuild build"
  },
  "dependencies": {
    "axios": "^1.7.7",
    "mpegts.js": "^1.7.3",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@rsbuild/core": "^1.0.0",
    "@rsbuild/plugin-react": "^1.0.0",
    "typescript": "^5.6.0"
  }
}
```

- [ ] **Step 2: 写 `rsbuild.config.ts`**

```ts
import { defineConfig } from '@rsbuild/core';
import { pluginReact } from '@rsbuild/plugin-react';

export default defineConfig({
  plugins: [pluginReact()],
  html: { template: './src/index.html' },
  source: { entry: { index: './src/index.tsx' } },
  server: { port: 3000, proxy: { '/api': 'http://localhost:5180' } },
  output: { distPath: { root: 'dist' } },
});
```

- [ ] **Step 3: 写 `tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["DOM", "DOM.Iterable", "ES2020"],
    "jsx": "react-jsx",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "noEmit": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "types": ["@rsbuild/core/types"]
  },
  "include": ["src"]
}
```

- [ ] **Step 4: 写 `src/index.html` + `src/index.tsx`**

`index.html`:
```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
    <title>IPTV 聚合服务</title>
  </head>
  <body><div id="root"></div></body>
</html>
```

`index.tsx`:
```tsx
import { createRoot } from 'react-dom/client';
import App from './App';
import './index.css';

createRoot(document.getElementById('root')!).render(<App />);
```

- [ ] **Step 5: 写 `src/types.ts`**

```ts
export interface Source {
  id: number; name: string; url: string; type: 'm3u' | 'txt';
  enabled: number; use_proxy: number; sort: number; note: string;
  fail_count: number; last_ok_at: string | null;
}
export interface Alias {
  id: number; canonical: string; pattern: string; is_regex: number; enabled: number;
}
export interface Template {
  id: number; canonical: string; group_title: string; logo: string;
  sort: number; enabled: number;
}
export interface Channel {
  id: number; name: string; group_title: string; url: string; logo: string;
  tvg_id: string; tvg_name: string; source: string; status: string;
  detail: string; resolution: number; speed: number; delay: number;
}
export interface TaskStatus {
  status: string; stage: string; run_id: number | null;
  started_at: string | null; logs: string[];
}
export interface Schedule {
  update_mode: 'interval' | 'time'; update_interval: number;
  update_times: string[]; update_startup: boolean; time_zone: string;
}
export interface Report {
  groups: Record<string, number>; resolution: Record<string, number>;
  sources: Source[]; runs: Array<{ id: number; started_at: string;
    finished_at: string | null; status: string; stats_json: string }>;
}
```

- [ ] **Step 6: 写 `src/api.ts`**

```ts
import axios from 'axios';
import type { Source, Alias, Template, Channel, TaskStatus, Schedule, Report } from './types';

const http = axios.create({ baseURL: '/api' });

export const listSources = () => http.get<Source[]>('/sources').then(r => r.data);
export const createSource = (d: Partial<Source>) => http.post('/sources', d).then(r => r.data);
export const updateSource = (id: number, d: Partial<Source>) => http.put(`/sources/${id}`, d).then(r => r.data);
export const deleteSource = (id: number) => http.delete(`/sources/${id}`).then(r => r.data);

export const listAliases = () => http.get<Alias[]>('/aliases').then(r => r.data);
export const createAlias = (d: Partial<Alias>) => http.post('/aliases', d).then(r => r.data);
export const updateAlias = (id: number, d: Partial<Alias>) => http.put(`/aliases/${id}`, d).then(r => r.data);
export const deleteAlias = (id: number) => http.delete(`/aliases/${id}`).then(r => r.data);

export const listTemplates = () => http.get<Template[]>('/templates').then(r => r.data);
export const createTemplate = (d: Partial<Template>) => http.post('/templates', d).then(r => r.data);
export const updateTemplate = (id: number, d: Partial<Template>) => http.put(`/templates/${id}`, d).then(r => r.data);
export const deleteTemplate = (id: number) => http.delete(`/templates/${id}`).then(r => r.data);

export const listChannels = (run = 'latest') => http.get<Channel[]>('/channels', { params: { run } }).then(r => r.data);
export const getReport = () => http.get<Report>('/reports').then(r => r.data);

export const runTask = () => http.post('/tasks/run').then(r => r.data);
export const getStatus = () => http.get<TaskStatus>('/tasks/status').then(r => r.data);
export const getSchedule = () => http.get<Schedule>('/tasks/schedule').then(r => r.data);
export const setSchedule = (d: Partial<Schedule>) => http.put('/tasks/schedule', d).then(r => r.data);
export const logsUrl = () => '/api/tasks/logs';  // for EventSource
export const playlistUrls = () => ({ full: '/full.m3u', compact: '/compact.m3u', txt: '/iptv.txt' });
```

- [ ] **Step 7: 写 `src/icons.tsx`**（内联 SVG，Sun/Moon/Play/Trash/Plus/Copy）

```tsx
export const Sun = () => (<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>);
export const Moon = () => (<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z" /></svg>);
export const Play = () => (<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>);
export const Trash = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14" /></svg>);
export const Plus = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 5v14M5 12h14" /></svg>);
export const Copy = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V5a2 2 0 0 1 2-2h10" /></svg>);
```

- [ ] **Step 8: 写 `src/index.css`**（照搬 Frostcast visionOS 变量系统）

```css
:root{
  --bg:#08090e; --glass:rgba(255,255,255,0.05); --glass-mid:rgba(255,255,255,0.08);
  --glass-strong:rgba(255,255,255,0.14); --menu-bg:rgba(24,26,34,0.8);
  --fg:rgba(255,255,255,0.92); --fg2:rgba(255,255,255,0.55); --muted:rgba(255,255,255,0.35);
  --border:rgba(255,255,255,0.06); --border-strong:rgba(255,255,255,0.12);
  --accent:#E8735A; --accent-soft:rgba(232,115,90,0.16);
  --danger:#ff6b6b; --danger-soft:rgba(255,107,107,0.14);
  --font:'SF Pro Display',-apple-system,BlinkMacSystemFont,system-ui,'Segoe UI',sans-serif;
  --blur:blur(40px) saturate(180%);
  --r-card:16px; --r-ctl:12px; --r-pill:99px;
  --inset:inset 0 1px 0 rgba(255,255,255,0.05);
  --card-shadow:0 8px 30px rgba(0,0,0,.35);
}
:root[data-theme="light"]{
  --bg:#e7e9f0; --glass:rgba(255,255,255,0.55); --glass-mid:rgba(255,255,255,0.7);
  --glass-strong:rgba(255,255,255,0.85); --menu-bg:rgba(255,255,255,0.9);
  --fg:rgba(20,22,28,0.92); --fg2:rgba(20,22,28,0.6); --muted:rgba(20,22,28,0.4);
  --border:rgba(0,0,0,0.08); --border-strong:rgba(0,0,0,0.14);
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font-family:var(--font);
  transition:background .3s,color .3s;min-height:100vh;
  padding:env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left);}
body::before{content:'';position:fixed;inset:0;z-index:-1;pointer-events:none;
  background:radial-gradient(60% 50% at 20% 10%,var(--accent-soft),transparent),
             radial-gradient(50% 40% at 90% 20%,rgba(90,140,232,.14),transparent);}
.glass{background:var(--glass);backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);
  border:1px solid var(--border);box-shadow:var(--inset);}
header{display:flex;align-items:center;gap:16px;padding:16px clamp(12px,4vw,32px);
  position:sticky;top:0;z-index:10;background:var(--glass);backdrop-filter:var(--blur);
  border-bottom:1px solid var(--border);}
.brand{font-weight:700;font-size:clamp(16px,2.5vw,20px);}
.tools{margin-left:auto;display:flex;align-items:center;gap:10px;}
.seg{display:flex;background:var(--glass);border:1px solid var(--border);border-radius:var(--r-pill);
  padding:3px;backdrop-filter:var(--blur);}
.seg button{border:0;background:transparent;color:var(--fg2);padding:7px 14px;border-radius:var(--r-pill);
  cursor:pointer;font-size:13px;transition:.2s;}
.seg button.active{background:var(--accent);color:#fff;}
.icon-btn{width:38px;height:38px;display:grid;place-items:center;border-radius:var(--r-pill);
  border:1px solid var(--border);background:var(--glass);color:var(--fg);cursor:pointer;}
main{padding:clamp(12px,4vw,32px);max-width:1200px;margin:0 auto;}
.card{background:var(--glass);border:1px solid var(--border);border-radius:var(--r-card);
  padding:16px;box-shadow:var(--card-shadow);margin-bottom:14px;}
table{width:100%;border-collapse:collapse;font-size:13px;}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--border);}
input,select{background:var(--glass-mid);border:1px solid var(--border);color:var(--fg);
  border-radius:var(--r-ctl);padding:8px 10px;font-size:13px;font-family:var(--font);}
.btn{border:1px solid var(--border-strong);background:var(--glass-strong);color:var(--fg);
  border-radius:var(--r-ctl);padding:8px 14px;cursor:pointer;font-size:13px;}
.btn.primary{background:var(--accent);border-color:var(--accent);color:#fff;}
.btn.danger{background:var(--danger-soft);border-color:var(--danger);color:var(--danger);}
.grid-ch{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,240px),1fr));gap:12px;}
.logs{font-family:ui-monospace,monospace;font-size:12px;background:rgba(0,0,0,.3);
  border-radius:var(--r-ctl);padding:12px;height:320px;overflow:auto;white-space:pre-wrap;}
.overlay{position:fixed;inset:0;z-index:100;background:rgba(0,0,0,.85);display:grid;place-items:center;}
.overlay video{max-width:96vw;max-height:90vh;border-radius:12px;}
@media (max-width:560px){ main{padding:12px} th:nth-child(n+4),td:nth-child(n+4){display:none} }
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
```

- [ ] **Step 9: 装依赖并构建**

Run: `cd frontend && bun install && bun run build:dev`
Expected: 生成 `frontend/dist/`（含 `index.html` + `static/`），无编译错误

- [ ] **Step 10: Commit**

```bash
git add frontend/package.json frontend/rsbuild.config.ts frontend/tsconfig.json frontend/src/index.html frontend/src/index.tsx frontend/src/index.css frontend/src/api.ts frontend/src/types.ts frontend/src/icons.tsx && git commit -m "feat: frontend scaffold — rsbuild, theme CSS, api client, types"
```

---

## Task 19: App.tsx（外壳 + 主题切换 + tab 分段控件）

**Files:**
- Create: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `icons.tsx`；渲染各 Panel（Task 20-23，先用占位，随任务替换）。
- Produces: 单页控制器，`tab` 状态 ∈ `sources|aliases|templates|task|channels|report`，`theme` 存 localStorage，`document.documentElement[data-theme]`。

- [ ] **Step 1: 写 `App.tsx`**

```tsx
import { useEffect, useState } from 'react';
import { Sun, Moon } from './icons';
import SourcesPanel from './components/SourcesPanel';
import AliasPanel from './components/AliasPanel';
import TemplatePanel from './components/TemplatePanel';
import TaskPanel from './components/TaskPanel';
import ChannelsPanel from './components/ChannelsPanel';
import ReportPanel from './components/ReportPanel';

type Tab = 'sources' | 'aliases' | 'templates' | 'task' | 'channels' | 'report';
const TABS: { k: Tab; label: string }[] = [
  { k: 'sources', label: '源' }, { k: 'aliases', label: '别名' },
  { k: 'templates', label: '模板' }, { k: 'task', label: '任务' },
  { k: 'channels', label: '频道' }, { k: 'report', label: '报告' },
];

export default function App() {
  const [tab, setTab] = useState<Tab>('task');
  const [theme, setTheme] = useState<'dark' | 'light'>(
    () => (localStorage.getItem('iptv-theme') as 'dark' | 'light') || 'dark');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('iptv-theme', theme);
  }, [theme]);

  return (
    <>
      <header>
        <div className="brand">IPTV 聚合服务</div>
        <div className="tools">
          <div className="seg">
            {TABS.map(t => (
              <button key={t.k} className={tab === t.k ? 'active' : ''}
                onClick={() => setTab(t.k)}>{t.label}</button>
            ))}
          </div>
          <button className="icon-btn" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
            {theme === 'dark' ? <Sun /> : <Moon />}
          </button>
        </div>
      </header>
      <main>
        {tab === 'sources' && <SourcesPanel />}
        {tab === 'aliases' && <AliasPanel />}
        {tab === 'templates' && <TemplatePanel />}
        {tab === 'task' && <TaskPanel />}
        {tab === 'channels' && <ChannelsPanel />}
        {tab === 'report' && <ReportPanel />}
      </main>
    </>
  );
}
```

- [ ] **Step 2: 建占位组件**（让编译通过，后续任务替换内容）— 在 `frontend/src/components/` 建 `SourcesPanel.tsx AliasPanel.tsx TemplatePanel.tsx TaskPanel.tsx ChannelsPanel.tsx ReportPanel.tsx PlayerOverlay.tsx`，每个先写：

```tsx
export default function Panel() { return <div className="card">TODO</div>; }
```

（注意各文件默认导出名可保持 `Panel`，import 处用别名即可；PlayerOverlay 先导出接受 props 的空组件。）

- [ ] **Step 3: 构建验证**

Run: `cd frontend && bun run build:dev`
Expected: 编译通过

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/ && git commit -m "feat: App shell — theme toggle, tab segmented control, panel placeholders"
```

---

## Task 20: SourcesPanel + AliasPanel + TemplatePanel（CRUD 面板）

**Files:**
- Modify: `frontend/src/components/SourcesPanel.tsx`
- Modify: `frontend/src/components/AliasPanel.tsx`
- Modify: `frontend/src/components/TemplatePanel.tsx`

**Interfaces:**
- Consumes: `api.ts`（各 list/create/update/delete）、`types.ts`、`icons.tsx`。
- Produces: 三个可用 CRUD 面板。三者结构高度相似（表格 + 内联编辑 + 新增行 + 删除）。

- [ ] **Step 1: 写 `SourcesPanel.tsx`**

```tsx
import { useEffect, useState } from 'react';
import { listSources, createSource, updateSource, deleteSource } from '../api';
import type { Source } from '../types';
import { Plus, Trash } from '../icons';

const BLANK = { name: '', url: '', type: 'm3u' as const };

export default function SourcesPanel() {
  const [rows, setRows] = useState<Source[]>([]);
  const [draft, setDraft] = useState(BLANK);

  const reload = () => listSources().then(setRows);
  useEffect(() => { reload(); }, []);

  const add = async () => {
    if (!draft.name || !draft.url) return;
    await createSource(draft);
    setDraft(BLANK);
    reload();
  };
  const toggle = async (s: Source, field: 'enabled' | 'use_proxy') => {
    await updateSource(s.id, { [field]: s[field] ? 0 : 1 });
    reload();
  };
  const remove = async (id: number) => { await deleteSource(id); reload(); };

  return (
    <div className="card">
      <h3>抓取源</h3>
      <table>
        <thead><tr><th>名称</th><th>URL</th><th>类型</th><th>启用</th>
          <th>代理</th><th>失败</th><th>最近成功</th><th></th></tr></thead>
        <tbody>
          {rows.map(s => (
            <tr key={s.id}>
              <td>{s.name}</td>
              <td style={{ maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.url}</td>
              <td>{s.type}</td>
              <td><input type="checkbox" checked={!!s.enabled} onChange={() => toggle(s, 'enabled')} /></td>
              <td><input type="checkbox" checked={!!s.use_proxy} onChange={() => toggle(s, 'use_proxy')} /></td>
              <td>{s.fail_count}</td>
              <td>{s.last_ok_at?.slice(0, 16) || '-'}</td>
              <td><button className="btn danger" onClick={() => remove(s.id)}><Trash /></button></td>
            </tr>
          ))}
          <tr>
            <td><input value={draft.name} placeholder="名称"
              onChange={e => setDraft({ ...draft, name: e.target.value })} /></td>
            <td><input value={draft.url} placeholder="https://..."
              onChange={e => setDraft({ ...draft, url: e.target.value })} /></td>
            <td>
              <select value={draft.type}
                onChange={e => setDraft({ ...draft, type: e.target.value as 'm3u' | 'txt' })}>
                <option value="m3u">m3u</option><option value="txt">txt</option>
              </select>
            </td>
            <td colSpan={4} />
            <td><button className="btn primary" onClick={add}><Plus /></button></td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: 写 `AliasPanel.tsx`**

```tsx
import { useEffect, useState } from 'react';
import { listAliases, createAlias, updateAlias, deleteAlias } from '../api';
import type { Alias } from '../types';
import { Plus, Trash } from '../icons';

const BLANK = { canonical: '', pattern: '', is_regex: 0 };

export default function AliasPanel() {
  const [rows, setRows] = useState<Alias[]>([]);
  const [draft, setDraft] = useState(BLANK);
  const reload = () => listAliases().then(setRows);
  useEffect(() => { reload(); }, []);
  const add = async () => {
    if (!draft.canonical || !draft.pattern) return;
    await createAlias(draft); setDraft(BLANK); reload();
  };
  const toggleRegex = async (a: Alias) => {
    await updateAlias(a.id, { is_regex: a.is_regex ? 0 : 1 }); reload();
  };
  const remove = async (id: number) => { await deleteAlias(id); reload(); };

  return (
    <div className="card">
      <h3>频道别名（归一）</h3>
      <table>
        <thead><tr><th>规范名 canonical</th><th>匹配 pattern</th><th>正则</th><th></th></tr></thead>
        <tbody>
          {rows.map(a => (
            <tr key={a.id}>
              <td>{a.canonical}</td><td>{a.pattern}</td>
              <td><input type="checkbox" checked={!!a.is_regex} onChange={() => toggleRegex(a)} /></td>
              <td><button className="btn danger" onClick={() => remove(a.id)}><Trash /></button></td>
            </tr>
          ))}
          <tr>
            <td><input value={draft.canonical} placeholder="CCTV1"
              onChange={e => setDraft({ ...draft, canonical: e.target.value })} /></td>
            <td><input value={draft.pattern} placeholder="^CCTV[-\\s]?1"
              onChange={e => setDraft({ ...draft, pattern: e.target.value })} /></td>
            <td><input type="checkbox" checked={!!draft.is_regex}
              onChange={e => setDraft({ ...draft, is_regex: e.target.checked ? 1 : 0 })} /></td>
            <td><button className="btn primary" onClick={add}><Plus /></button></td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 3: 写 `TemplatePanel.tsx`**

```tsx
import { useEffect, useState } from 'react';
import { listTemplates, createTemplate, deleteTemplate } from '../api';
import type { Template } from '../types';
import { Plus, Trash } from '../icons';

const BLANK = { canonical: '', group_title: '', logo: '', sort: 0 };

export default function TemplatePanel() {
  const [rows, setRows] = useState<Template[]>([]);
  const [draft, setDraft] = useState(BLANK);
  const reload = () => listTemplates().then(setRows);
  useEffect(() => { reload(); }, []);
  const add = async () => {
    if (!draft.canonical) return;
    await createTemplate(draft); setDraft(BLANK); reload();
  };
  const remove = async (id: number) => { await deleteTemplate(id); reload(); };

  return (
    <div className="card">
      <h3>频道模板菜单（空=收录全部）</h3>
      <table>
        <thead><tr><th>频道</th><th>分组</th><th>台标</th><th>排序</th><th></th></tr></thead>
        <tbody>
          {rows.map(t => (
            <tr key={t.id}>
              <td>{t.canonical}</td><td>{t.group_title}</td>
              <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>{t.logo}</td>
              <td>{t.sort}</td>
              <td><button className="btn danger" onClick={() => remove(t.id)}><Trash /></button></td>
            </tr>
          ))}
          <tr>
            <td><input value={draft.canonical} placeholder="CCTV1"
              onChange={e => setDraft({ ...draft, canonical: e.target.value })} /></td>
            <td><input value={draft.group_title} placeholder="央视"
              onChange={e => setDraft({ ...draft, group_title: e.target.value })} /></td>
            <td><input value={draft.logo} placeholder="http://logo"
              onChange={e => setDraft({ ...draft, logo: e.target.value })} /></td>
            <td><input type="number" value={draft.sort} style={{ width: 60 }}
              onChange={e => setDraft({ ...draft, sort: Number(e.target.value) })} /></td>
            <td><button className="btn primary" onClick={add}><Plus /></button></td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 4: 构建验证**

Run: `cd frontend && bun run build:dev`
Expected: 编译通过

- [ ] **Step 5: 手动验证（可选，需后端在跑）**

Run: 后端 `python run_dev.py` + 浏览器打开 `http://localhost:5180`，切到「源」，确认 5 个种子源显示、可增删改、启禁开关生效。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/SourcesPanel.tsx frontend/src/components/AliasPanel.tsx frontend/src/components/TemplatePanel.tsx && git commit -m "feat: sources/alias/template CRUD panels"
```

---

## Task 21: TaskPanel（立即运行 + SSE 实时日志 + 阶段进度 + 调度设置）

**Files:**
- Modify: `frontend/src/components/TaskPanel.tsx`

**Interfaces:**
- Consumes: `api.ts`（`runTask/getStatus/getSchedule/setSchedule/logsUrl`）、`types.ts`。
- Produces: 运行按钮（忙时禁用）、`EventSource` 实时日志窗、当前 stage 徽标、调度表单（mode/interval/times/startup/timezone）。

- [ ] **Step 1: 写 `TaskPanel.tsx`**

```tsx
import { useEffect, useRef, useState } from 'react';
import { runTask, getStatus, getSchedule, setSchedule, logsUrl } from '../api';
import type { Schedule } from '../types';

export default function TaskPanel() {
  const [logs, setLogs] = useState<string[]>([]);
  const [stage, setStage] = useState('');
  const [status, setStatus] = useState('idle');
  const [sched, setSched] = useState<Schedule | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getSchedule().then(setSched);
    const es = new EventSource(logsUrl());
    es.onmessage = e => setLogs(prev => [...prev.slice(-500), e.data]);
    const poll = setInterval(() => {
      getStatus().then(s => { setStage(s.stage); setStatus(s.status); });
    }, 1500);
    return () => { es.close(); clearInterval(poll); };
  }, []);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  const run = async () => {
    try { await runTask(); } catch { alert('已有任务在运行'); }
  };
  const saveSched = async () => { if (sched) { await setSchedule(sched); alert('已保存'); } };

  return (
    <>
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button className="btn primary" onClick={run} disabled={status === 'running'}>
            {status === 'running' ? '运行中…' : '立即运行'}
          </button>
          <span>状态: {status}</span>
          {stage && <span className="seg"><button className="active">{stage}</button></span>}
        </div>
        <div ref={logRef} className="logs" style={{ marginTop: 12 }}>
          {logs.join('\n')}
        </div>
      </div>
      {sched && (
        <div className="card">
          <h3>调度设置</h3>
          <div style={{ display: 'grid', gap: 10, maxWidth: 420 }}>
            <label>模式
              <select value={sched.update_mode}
                onChange={e => setSched({ ...sched, update_mode: e.target.value as 'interval' | 'time' })}>
                <option value="interval">interval（间隔小时）</option>
                <option value="time">time（每日定点）</option>
              </select>
            </label>
            {sched.update_mode === 'interval' ? (
              <label>间隔(小时)
                <input type="number" value={sched.update_interval}
                  onChange={e => setSched({ ...sched, update_interval: Number(e.target.value) })} />
              </label>
            ) : (
              <label>定点(逗号分隔 HH:MM)
                <input value={sched.update_times.join(',')}
                  onChange={e => setSched({ ...sched, update_times: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })} />
              </label>
            )}
            <label>时区
              <input value={sched.time_zone}
                onChange={e => setSched({ ...sched, time_zone: e.target.value })} />
            </label>
            <label><input type="checkbox" checked={sched.update_startup}
              onChange={e => setSched({ ...sched, update_startup: e.target.checked })} /> 启动即跑</label>
            <button className="btn" onClick={saveSched}>保存调度</button>
          </div>
        </div>
      )}
    </>
  );
}
```

- [ ] **Step 2: 构建验证**

Run: `cd frontend && bun run build:dev`
Expected: 编译通过

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/TaskPanel.tsx && git commit -m "feat: task panel — run trigger, SSE live logs, stage badge, schedule form"
```

---

## Task 22: ChannelsPanel + PlayerOverlay（频道网格 + mpegts.js 试播 + 订阅地址）

**Files:**
- Modify: `frontend/src/components/ChannelsPanel.tsx`
- Modify: `frontend/src/components/PlayerOverlay.tsx`

**Interfaces:**
- Consumes: `api.ts`（`listChannels/playlistUrls`）、`types.ts`。
- Produces:
  - `PlayerOverlay`（props: `{ url: string; name: string; onClose: () => void }`；`.ts`/`.m3u8`/mpegts 用动态 `import('mpegts.js')` MSE 播放，出错回退原生 `<video src>`；Esc 关闭）
  - `ChannelsPanel`（顶部展示 3 个订阅地址可复制；频道网格：名称/分组/分辨率/速率/状态 + 试播按钮）

- [ ] **Step 1: 写 `PlayerOverlay.tsx`**

```tsx
import { useEffect, useRef } from 'react';

interface Props { url: string; name: string; onClose: () => void; }

export default function PlayerOverlay({ url, name, onClose }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    let player: any;
    let cancelled = false;
    const video = videoRef.current!;
    (async () => {
      const isTs = /\.(ts|m3u8)(\?|$)/i.test(url) || url.startsWith('mpegts');
      if (isTs) {
        try {
          const mpegts = (await import('mpegts.js')).default;
          if (cancelled) return;
          if (mpegts.isSupported()) {
            player = mpegts.createPlayer({ type: 'mse', isLive: true, url });
            player.attachMediaElement(video);
            player.load();
            player.play().catch(() => {});
            return;
          }
        } catch { /* fall through to native */ }
      }
      video.src = url;
      video.play().catch(() => {});
    })();
    return () => {
      cancelled = true;
      window.removeEventListener('keydown', onKey);
      if (player) { try { player.destroy(); } catch { /* noop */ } }
    };
  }, [url, onClose]);

  return (
    <div className="overlay" onClick={onClose}>
      <div onClick={e => e.stopPropagation()} style={{ textAlign: 'center' }}>
        <div style={{ color: '#fff', marginBottom: 8 }}>{name}</div>
        <video ref={videoRef} controls autoPlay playsInline />
        <div style={{ marginTop: 10 }}>
          <button className="btn" onClick={onClose}>关闭 (Esc)</button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 写 `ChannelsPanel.tsx`**

```tsx
import { useEffect, useState } from 'react';
import { listChannels, playlistUrls } from '../api';
import type { Channel } from '../types';
import { Play, Copy } from '../icons';
import PlayerOverlay from './PlayerOverlay';

export default function ChannelsPanel() {
  const [rows, setRows] = useState<Channel[]>([]);
  const [playing, setPlaying] = useState<Channel | null>(null);
  const urls = playlistUrls();

  useEffect(() => { listChannels('latest').then(setRows); }, []);
  const copy = (path: string) => navigator.clipboard.writeText(location.origin + path);

  return (
    <>
      <div className="card">
        <h3>订阅地址</h3>
        {(['full', 'compact', 'txt'] as const).map(k => (
          <div key={k} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
            <code style={{ flex: 1 }}>{location.origin + urls[k]}</code>
            <button className="btn" onClick={() => copy(urls[k])}><Copy /></button>
          </div>
        ))}
      </div>
      <div className="card">
        <h3>频道（{rows.length}）</h3>
        <div className="grid-ch">
          {rows.map(c => (
            <div key={c.id} className="card" style={{ margin: 0 }}>
              <div style={{ fontWeight: 600 }}>{c.name}</div>
              <div style={{ color: 'var(--fg2)', fontSize: 12 }}>
                {c.group_title} · {c.resolution ? c.resolution + 'p' : '—'} ·
                {c.speed ? ` ${c.speed}M/s` : ''} · {c.status}
              </div>
              <button className="btn primary" style={{ marginTop: 8 }}
                onClick={() => setPlaying(c)}><Play /> 试播</button>
            </div>
          ))}
        </div>
      </div>
      {playing && <PlayerOverlay url={playing.url} name={playing.name}
        onClose={() => setPlaying(null)} />}
    </>
  );
}
```

- [ ] **Step 3: 构建验证**

Run: `cd frontend && bun run build:dev`
Expected: 编译通过

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ChannelsPanel.tsx frontend/src/components/PlayerOverlay.tsx && git commit -m "feat: channels grid + mpegts.js player overlay + subscription URLs"
```

---

## Task 23: ReportPanel（统计卡片）

**Files:**
- Modify: `frontend/src/components/ReportPanel.tsx`

**Interfaces:**
- Consumes: `api.ts`（`getReport`）、`types.ts`。
- Produces: 分组数、清晰度分布、源健康度、历史跑批四块卡片。

- [ ] **Step 1: 写 `ReportPanel.tsx`**

```tsx
import { useEffect, useState } from 'react';
import { getReport } from '../api';
import type { Report } from '../types';

export default function ReportPanel() {
  const [r, setR] = useState<Report | null>(null);
  useEffect(() => { getReport().then(setR); }, []);
  if (!r) return <div className="card">加载中…</div>;

  return (
    <>
      <div className="card">
        <h3>清晰度分布</h3>
        {Object.entries(r.resolution).map(([k, v]) => (
          <div key={k}>{k}: {v}</div>
        ))}
      </div>
      <div className="card">
        <h3>分组统计（{Object.keys(r.groups).length} 组）</h3>
        {Object.entries(r.groups).map(([k, v]) => (
          <span key={k} className="seg" style={{ margin: 2, display: 'inline-flex' }}>
            <button>{k}: {v}</button>
          </span>
        ))}
      </div>
      <div className="card">
        <h3>源健康度</h3>
        <table>
          <thead><tr><th>源</th><th>启用</th><th>失败次数</th><th>最近成功</th></tr></thead>
          <tbody>{r.sources.map(s => (
            <tr key={s.id}><td>{s.name}</td><td>{s.enabled ? '✓' : '✗'}</td>
              <td>{s.fail_count}</td><td>{s.last_ok_at?.slice(0, 16) || '-'}</td></tr>
          ))}</tbody>
        </table>
      </div>
      <div className="card">
        <h3>历史跑批</h3>
        <table>
          <thead><tr><th>#</th><th>开始</th><th>结束</th><th>状态</th><th>统计</th></tr></thead>
          <tbody>{r.runs.map(run => (
            <tr key={run.id}><td>{run.id}</td><td>{run.started_at?.slice(0, 16)}</td>
              <td>{run.finished_at?.slice(0, 16) || '-'}</td><td>{run.status}</td>
              <td>{run.stats_json}</td></tr>
          ))}</tbody>
        </table>
      </div>
    </>
  );
}
```

- [ ] **Step 2: 构建验证**

Run: `cd frontend && bun run build:dev`
Expected: 编译通过

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ReportPanel.tsx && git commit -m "feat: report panel — resolution/group stats, source health, run history"
```

---

## Task 24: start_dev.sh + Dockerfile + docker-compose + .dockerignore

**Files:**
- Create: `start_dev.sh`（repo 根）
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`

**Interfaces:**
- Consumes: 全部后端 + 前端产物。
- Produces: 一键开发脚本 + 单镜像多阶段构建 + 单端口 compose。

- [ ] **Step 1: 写 `start_dev.sh`**（仿 Frostcast，端口默认 5180）

```bash
#!/bin/bash
set -e
PORT="${1:-5180}"; export PORT
command -v bun >/dev/null 2>&1 || { echo "错误: 未找到 bun"; exit 1; }
command -v uv  >/dev/null 2>&1 || { echo "错误: 未找到 uv"; exit 1; }

cd "$(dirname "$0")/frontend"
bun install
bun run build:dev
bun run build:dev -- --watch &
FRONTEND_PID=$!

cd ../backend
[ ! -f config.yaml ] && [ -f config.yaml.example ] && cp config.yaml.example config.yaml
[ ! -d .venv ] && uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
python run_dev.py &
BACKEND_PID=$!

trap "kill $FRONTEND_PID $BACKEND_PID 2>/dev/null; exit" INT
wait
```

- [ ] **Step 2: `chmod +x start_dev.sh`**

Run: `chmod +x start_dev.sh`

- [ ] **Step 3: 写 `Dockerfile`**（多阶段：bun 构建前端 → python3.13-slim + ffmpeg 运行）

```dockerfile
# Stage 1: frontend
FROM oven/bun:1-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json ./
RUN bun install
COPY frontend/ ./
RUN bun run build

# Stage 2: production
FROM python:3.13-slim AS production
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
COPY backend/requirements.txt ./
RUN uv pip install --system -r requirements.txt
COPY backend/ ./
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
ENV FRONTEND=/app/frontend/dist
ENV PORT=5180
ENV OUTPUT_DIR=/app/output
ENV DB_PATH=/app/data/iptv.db
RUN mkdir -p /app/logs /app/output /app/data
EXPOSE 5180
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5180/api/tasks/status')" || exit 1
CMD ["python", "run_prod.py"]
```

- [ ] **Step 4: 写 `docker-compose.yml`**

```yaml
services:
  iptv:
    build: .
    ports:
      - "5180:5180"
    volumes:
      - ./config.yaml:/app/config.yaml
      - ./data:/app/data
      - ./output:/app/output
    restart: unless-stopped
```

- [ ] **Step 5: 写 `.dockerignore`**

```
**/node_modules
**/dist
**/.venv
**/__pycache__
**/*.pyc
backend/config.yaml
data
output
logs
.git
docs
sources
```

- [ ] **Step 6: 构建验证**

Run: `docker build -t iptv:test .`
Expected: 两阶段构建成功，镜像生成（含 ffmpeg）

- [ ] **Step 7: 端到端冒烟（可选）**

Run: `docker compose up -d && sleep 5 && curl -s localhost:5180/api/tasks/status`
Expected: 返回 JSON（`status` 字段存在）

- [ ] **Step 8: Commit**

```bash
git add start_dev.sh Dockerfile docker-compose.yml .dockerignore && git commit -m "feat: dev launcher + multi-stage Docker image + compose (single port, ffmpeg)"
```

---

## Self-Review

**1. Spec coverage**（逐节核对）：

- §1 目标 → 全部落地：Web 界面(Task 19-23)、两阶段检测(Task 9+10)、m3u/txt 直出(Task 15)、源可扩展(Task 2 seed + Task 13 CRUD)、定时(Task 17)、单镜像(Task 24)、Guovin 特性(见 §9 映射，下文)。
- §2 技术栈 → requirements(Task 1)、前端依赖(Task 18)、SSE(Task 14)、Docker(Task 24)、start_dev(Task 24)。
- §3 目录结构 → File Structure 段 + 各 Task 的 Files 覆盖每个文件。
- §4 SQLite Schema → Task 2（5 表字段逐一对应，种子 5 源 + 别名）。
- §5 数据流 runner.run → Task 11（10 步 + 单跑批锁在 run_service Task 12 + emit 事件）。
- §6 HTTP 接口 → 公开路由(Task 15)、API(Task 13/14)、单端口托管 create_app(Task 16)。
- §7 前端 6 面板 + 视觉 → Task 18(CSS)/19(壳)/20-23(面板)。
- §8 配置 → Task 1 config.yaml.example 逐字。
- §9 Guovin 特性映射 → 模板+别名(Task 4)、urls_limit(Task 6)、测速+sort_by(Task 10+6)、广告过滤(Task 9)、阈值(Task 6)、源自动停用(Task 11)、历史合并(Task 11)、EPG+台标(Task 3 提取 + Task 7 写入)、调度增强(Task 17)。全覆盖。
- §10 Docker + start_dev → Task 24。
- §11 错误处理/测试 → 单源失败不中断(Task 8)、run failed 释放锁(Task 11+12)、ffprobe 缺失降级(Task 10)、pytest 覆盖纯函数 + 路由(每个 pipeline Task + Task 16)。

无遗漏。

**2. Placeholder scan**：Task 19 Step 2 的 `TODO` 占位组件是**刻意的中间脚手架**（下一任务立即替换，便于 App.tsx 先编译），非计划失败；已在步骤中说明替换时机。其余步骤均含完整代码/命令/预期输出。

**3. Type consistency**（跨任务签名核对）：
- `Entry` dataclass 字段（Task 3）被 parse/normalize/dedup/filter_sort/output/check_* 一致消费；`resolution:int(高度)`、`speed:float`、`delay:float` 命名贯穿 Task 6/10/11/DB schema/前端 types。
- `runner.run(on_event=...)`（Task 11）↔ `run_service.push_log(msg, stage)`（Task 12）↔ SSE(Task 14) 签名一致。
- `scheduler.get_schedule/set_schedule/start/shutdown`（Task 17）↔ tasks 路由(Task 14)与 app.py(Task 16) 调用一致。
- DB 列名（Task 2）↔ services 查询(Task 12)↔ 前端 types(Task 18) 三处对齐（`group_title`、`fail_count`、`last_ok_at` 等）。
- API 路径（Task 13/14/15）↔ `api.ts`(Task 18) 路径逐一对应。

**已知设计决策（非缺陷）**：`fetch.py`/`check_http.py` 使用 `httpx ... verify=False` 关闭 TLS 校验，沿用原 `iptv_cn.py` 对公共 IPTV 源（常见自签/坏证书）的既有行为，属明确的领域取舍；生产环境若需收紧，可将 `verify` 提为配置项，但这超出本 spec 范围（YAGNI）。

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-07-24-iptv-aggregation-service.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - 每个任务派一个全新子代理实现，任务间做两阶段复核（spec 合规 + 代码质量），迭代快、上下文干净。

**2. Inline Execution** - 在本会话内逐任务执行，用 executing-plans 做批量 + 检查点复核。

**Which approach?**