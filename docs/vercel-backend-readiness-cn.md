# CalmWay Vercel 后端就绪说明

本文只记录 FastAPI 后端的 Vercel 部署准备；本阶段没有创建、关联或部署
Vercel 项目，也没有修改 Neon 数据或实现定时刷新。

## 1. Vercel 项目目录

- 后续在 Vercel 中把 **Root Directory** 精确设置为 `backend`。
- 使用 Vercel 对 FastAPI 的原生检测，不添加 `vercel.json` 或旧式
  `builds` 配置。
- Vercel 官方支持在项目根目录从 `index.py` 检测名为 `app` 的 FastAPI
  实例：[FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi)。

## 2. FastAPI 入口

Vercel 入口是 `backend/index.py`：

```python
from app.main import app
```

它只重新导出现有 `backend/app/main.py` 中的 ASGI 应用，不创建第二个
FastAPI 实例、不复制路由，也不改变本地启动命令。

## 3. 生产环境变量

Vercel Production 和需要联调的 Preview 环境必须分别配置：

| 变量 | 值的来源与要求 |
| --- | --- |
| `DATABASE_URL` | Neon 控制台提供的 **pooled** PostgreSQL 连接串；必须保密 |
| `MAPBOX_ACCESS_TOKEN` | 后端 Mapbox token；必须保密，不能使用 `VITE_` 前缀 |
| `FRONTEND_ORIGINS` | 已部署前端的完整 origin；多个 origin 用英文逗号分隔 |

其余配置已有项目默认值，不是当前生产启动的必填变量。仓库根目录
`.env.example` 只包含本地示例或空占位符；真实值继续保存在未跟踪的
`backend/.env` 或部署平台环境变量中。

## 4. Neon pooled 与 direct 的边界

- 数据迁移、DDL、批量导入及人工管理使用 Neon **direct** 连接。
- Vercel 请求运行时的 `DATABASE_URL` 使用 Neon **pooled** 连接，由 Neon
  PgBouncer 复用数据库连接。官方说明见
  [Neon connection pooling](https://neon.com/docs/connect/connection-pooling)。
- 代码同时接受 `postgresql://...`（自动选择 psycopg 3）和
  `postgresql+psycopg://...`，不会记录或输出连接串。
- 本地环境保留 SQLAlchemy 原有连接池默认值。Vercel 自动提供
  `VERCEL=1` 时，每个 warm function instance 只保留 1 个 SQLAlchemy
  连接、禁止 overflow，并在 300 秒后回收连接；路由采样仍可在一次请求中
  复用连接，而不是为每个 50 m 样本重新握手。连接复用的主体仍是 Neon
  pooled endpoint。

## 5. CORS 生产配置

本地默认继续允许 `http://localhost:5173` 和
`http://127.0.0.1:5173`。生产环境通过 `FRONTEND_ORIGINS` 注入实际前端
origin，不预猜或硬编码 Vercel URL。当前配置不允许 credentials，也不使用
通配 origin；`GET`、`POST` 以及 Starlette CORS middleware 处理的
`OPTIONS /api/v1/routes/walking` 预检保持可用。

## 6. 本地开发行为

- 现有、被 `.gitignore` 忽略的 `backend/.env` 不变；未注入临时生产 URL
  时，仍使用开发者现有 Docker PostgreSQL/PostGIS `DATABASE_URL`。
- 从仓库根目录仍可运行：

  ```powershell
  .\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
  ```

- 从 `backend` 目录验证 Vercel 入口：

  ```powershell
  ..\.venv\Scripts\python.exe -c "from index import app; print(app.title)"
  ```

- `backend/.python-version` 固定为 Vercel 当前正式支持的 Python 3.12；官方
  支持的版本声明方式见
  [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python)。

## 7. Serverless 文件系统与后台进程审计

**PASS**：HTTP runtime request path 不写本地持久文件。启动阶段只读取可选
`.env`；运行状态仅有可丢弃的进程内缓存和惰性 SQLAlchemy engine，正确性
不依赖实例持续存在。

**PASS**：FastAPI 没有 startup/lifespan ingestion、baseline rebuild、
current-data refresh、scheduler 或后台线程，也不依赖 Docker 常驻进程。
`scripts/`、测试 fixture 及 ingestion 服务是离线/本地数据准备能力，不是
部署请求启动流程。

## 8. 后续部署步骤（本阶段不执行）

1. 在 Vercel Dashboard 导入对应 Git 仓库并创建独立后端项目。
2. 将项目 Root Directory 设置为 `backend`，保留原生 FastAPI 检测和默认
   Build/Output 设置。
3. 在目标 Preview/Production 环境分别添加敏感的 pooled
   `DATABASE_URL`、敏感的 `MAPBOX_ACCESS_TOKEN`，以及准确的
   `FRONTEND_ORIGINS`；不把值写入仓库。
4. 触发 Preview deployment，先检查 build/runtime 日志中没有 secret，
   再验证 `GET /health`、`GET /docs`、`GET /api/v1/crowd/point`、
   `POST /api/v1/routes/walking` 和生产 origin 的 OPTIONS 预检。
5. 使用真实前端完成一次 Route Search 到 Route summary 的端到端验收，并
   确认后端 Mapbox token 没有出现在浏览器 bundle 或响应中。
6. Preview 验收通过后才创建 Production deployment，并重复健康、CORS、
   数据库和 Mapbox 路由检查。

## 9. 回滚与本地恢复

- 若部署异常，在 Vercel 中把生产流量回滚到最后一个健康 deployment；若
  尚无健康版本，则撤销该后端域名/项目暴露并继续使用本地服务。
- 回滚应用部署不需要回滚数据库：本阶段无 schema 或数据变更。
- 本地恢复只需保留忽略的 `backend/.env` 中原 Docker URL，并使用原
  uvicorn 命令；不要把 Neon 凭证复制到 tracked `.env.example`。

## 10. 明确延期项目

GitHub Actions 每 15 分钟 current-activity refresh 明确延期到后续阶段。
本阶段没有 workflow、Vercel cron、scheduler、startup refresh 或 Neon
定时任务变更。
