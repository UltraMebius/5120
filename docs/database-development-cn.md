# CalmWay 本地数据库开发指南（Phase 2A-1）

CalmWay 使用 PostgreSQL 保存结构化行人传感器数据，并使用 PostGIS 支持后续的地理距离和范围查询。Phase 2A-1 只建立 FastAPI 到现有数据库的连接和只读验证，不摄取 City of Melbourne 数据，也不修改权威 schema。

Docker 在这里仅是本地开发基础设施，不代表云端部署。数据库结构的唯一来源仍是：

```text
handoff/epic1_backend_handoff_v3/05_DATABASE_SCHEMA.sql
```

## 1. 启动、查看和安全停止数据库

请在仓库根目录运行：

```powershell
docker compose -f .\handoff\epic1_backend_handoff_v3\17_docker-compose.yml start
docker compose -f .\handoff\epic1_backend_handoff_v3\17_docker-compose.yml ps
docker compose -f .\handoff\epic1_backend_handoff_v3\17_docker-compose.yml stop
```

`start` 会启动已经创建的本地容器，`stop` 会安全停止容器并保留数据库内容。

> 警告：除非确定要重置本地数据库，否则不要使用 `docker compose down -v`。其中 `-v` 会删除数据库 volume，已有本地数据和 schema 将无法从该 volume 恢复。

## 2. 配置 DATABASE_URL

后端使用 SQLAlchemy 2 和 psycopg 3。可以把仓库根目录的 `.env.example` 复制为 `.env`，或只为后端建立 `backend/.env`，然后配置：

```dotenv
DATABASE_URL=postgresql+psycopg://epic1:epic1@localhost:5432/epic1
```

`.env` 和 `backend/.env` 已由 `.gitignore` 忽略，不应执行 `git add -f`，也不要把真实密码放进 React、Vite 或任何 `VITE_` 变量。操作系统进程环境中的 `DATABASE_URL` 优先于 `.env` 文件。

如果旧配置使用 `postgresql://...`，后端会自动选择 psycopg 3；推荐新配置明确写成 `postgresql+psycopg://...`。缺少或无效的 `DATABASE_URL` 会产生清楚的数据库配置错误，不会回退到 SQLite。

## 3. 安装依赖并验证

在仓库根目录执行：

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
.\backend\.venv\Scripts\python.exe .\scripts\check_database.py
```

成功时会显示数据库连接、PostgreSQL/PostGIS 版本、schema 状态及缺失表。脚本只执行读取查询，不会建立表或写入测试记录；失败时返回非零退出码，并且不会打印数据库密码。

普通单元测试不要求 Docker 或 `DATABASE_URL`：

```powershell
.\backend\.venv\Scripts\python.exe -m pytest
```

明确运行真实数据库集成测试：

```powershell
$env:DATABASE_URL='postgresql+psycopg://epic1:epic1@localhost:5432/epic1'
.\backend\.venv\Scripts\python.exe -m pytest .\tests\integration\test_database_integration.py -v
```

集成测试只验证 `SELECT 1`、PostGIS 和权威 public 表是否存在；表中暂时没有 City of Melbourne 业务数据是正常状态。
