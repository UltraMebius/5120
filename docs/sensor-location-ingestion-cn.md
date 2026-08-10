# CalmWay 传感器位置导入指南（Phase 2A-2）

本阶段把 City of Melbourne 的公共行人计数器位置元数据导入本地 PostgreSQL/PostGIS。它只提供后续行人数据和空间计算需要的传感器主数据，不导入小时/分钟人数、不计算 Crowd Exposure，也不存储用户位置。

官方数据集标识符：

```text
pedestrian-counting-system-sensor-locations
```

程序使用 Explore API v2.1 的 `records` JSON 接口，每页最多读取 100 条，并按 `location_id` 排序、通过 `offset` 翻页，直到取得 `total_count` 指定的全部记录。这个小型参考数据集不需要 API key，也不抓取网页 HTML。

## 1. 先检查来源字段

运行 dry run：

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\import_sensor_locations.py --dry-run
```

该命令会访问真实 API，显示实际观察到的字段、总记录数、有效位置数和跳过原因，但不会连接或修改数据库。当前实现依据 live JSON 明确使用 `location_id`，不会猜测或改用 `sensor_id`。

观察到的字段映射如下：

| City live 字段 | CalmWay 目标 |
| --- | --- |
| `location_id` | `sensor.location_id`、`sensor_location_current.location_id` |
| `sensor_description` | `sensor_location_current.sensor_description` |
| `sensor_name` | `sensor_location_current.sensor_name` |
| `installation_date` | `sensor_location_current.installation_date` |
| `note` | `sensor_location_current.note` |
| `location_type` | `sensor_location_current.location_type`（原值保留，不推断 Indoor/Outdoor） |
| `status` | `sensor_location_current.status`（原值保留，不把全部记录改成 active） |
| `direction_1` / `direction_2` | `direction_1_label` / `direction_2_label` |
| `latitude` / `longitude` | 同名列 |
| `longitude`, `latitude` | `geom = POINT(X longitude, Y latitude)`，SRID 4326 |
| `location` | 用于核对嵌套 `lon`/`lat` 是否与顶层坐标一致，不另建列 |

live 数据没有提供可映射到 `source_updated_at` 的字段，因此该列保持 `NULL`；`first_seen_at`、`last_seen_at` 和 `loaded_at` 由数据库时间维护。

## 2. 真实导入

先按[本地数据库开发指南](database-development-cn.md)启动 Docker 并配置不提交到 Git 的 `DATABASE_URL`，然后执行：

```powershell
$env:DATABASE_URL='postgresql+psycopg://epic1:epic1@localhost:5432/epic1'
.\backend\.venv\Scripts\python.exe .\scripts\import_sensor_locations.py
```

写入在一个数据库事务中完成。`sensor` 和 `sensor_location_current` 都按 `location_id` upsert，因此重复运行不会产生重复传感器；来源名称、状态、备注或坐标改变时，当前快照会更新。未出现在本次来源中的旧传感器不会被删除，inactive 记录也不会被过滤。

如果记录有有效 `location_id` 但缺少/包含非法坐标，程序仍保留 `sensor` 主记录，但不会伪造 `(0, 0)` 或写入当前空间位置。若该 ID 以前有当前位置，则会删除该过时位置行，避免它继续提供虚假的空间支持。由于权威表的坐标、`location_type` 和 `geom` 均为非空，这类记录的其他位置元数据无法写入当前位置表，脚本会明确报告原因。

## 3. 验证

导入脚本会自动检查行数、重复 ID、SRID、经纬度顺序、Melbourne 范围、来源 ID 和 status 是否一致。也可以手动进入数据库执行只读 SQL：

```powershell
docker exec epic1-postgis psql -U epic1 -d epic1 -c "SELECT COUNT(*) FROM sensor;"
docker exec epic1-postgis psql -U epic1 -d epic1 -c "SELECT COUNT(*) FROM sensor_location_current;"
docker exec epic1-postgis psql -U epic1 -d epic1 -c "SELECT location_id, status, location_type, ST_SRID(geom::geometry), ST_X(geom::geometry) AS lon, ST_Y(geom::geometry) AS lat FROM sensor_location_current ORDER BY location_id LIMIT 5;"
```

行数会随 City live 数据变化，不应写死。以上是本地开发数据导入，不代表云端部署；不要提交 `.env`，不要在前端或日志中输出 `DATABASE_URL`。
