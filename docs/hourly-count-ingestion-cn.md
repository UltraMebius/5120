# CalmWay 历史小时行人数据导入指南（Phase 2A-3）

本阶段导入 City of Melbourne 官方“Pedestrian Counting System (counts per hour)”数据，数据集 ID 为：

```text
pedestrian-counting-system-monthly-counts-per-hour
```

目标仅是权威表 `pedestrian_hourly_count`。本阶段不建立 Local/Network baseline，不计算 percentile、Crowd Level，也不导入分钟数据。

## 1. 小时数据与分钟数据不同

官方小时数据明确规定：某个小时没有行人经过时，会保存 `pedestriancount = 0`。因此 0 是真实观测值，不能当成缺失值。缺少或无法解析的 count 也不能擅自改成 0。分钟来源的“缺记录”规则属于后续阶段，不适用于这里。

## 2. 日期范围必须显式提供

交接证据审计了 `2024-08-08` 至 `2026-08-07`，V5/V5B 使用：

- 训练：`2024-08-08` 至 `2026-02-07`；
- holdout：`2026-02-08` 至 `2026-08-07`。

但是交接配置没有把该范围声明为生产导入的固定默认值。程序不会猜测“最近一年/两年”，也不会自动导入 2009 年以来的全部 archive。每次 dry run 和真实导入都必须明确提供 `--start-date`、`--end-date`；完整生产范围需要团队/DS 确认。

## 3. 官方来源与字段映射

程序使用带服务端日期过滤的官方 CSV export，并逐行读取，不把约 160 万条完整 archive 一次载入内存。数据库按最多 1000 行的 transaction batch upsert。

| live 字段 | `pedestrian_hourly_count` |
| --- | --- |
| `location_id` | `location_id`，连接现有 `sensor.location_id` |
| `sensing_date` | `sensing_date`，Melbourne 本地日历日期 |
| `hourday` | `hour_day`，必须为 0–23 |
| 日期的 weekday | `day_type = Weekday/Weekend` |
| `id` | `source_id`，只用于来源追踪，不是数据库主键 |
| `direction_1`, `direction_2` | 同名可空方向计数；不是必填字段 |
| `pedestriancount` | `total_of_directions`，必须是非负整数，0 保留 |
| `sensor_name` | `source_sensor_name` |
| `location` | `source_location_text`，不声称它是历史几何模型 |

权威主键是 `(location_id, sensing_date, hour_day)`。重复导入会更新同一个逻辑小时，不会产生重复行。

## 4. Unknown 与迁移限制

历史数据可能包含当前 134 个位置快照中不存在的退休/迁移 sensor ID。交接没有提供这些 ID 的完整权威主数据或历史位置表，所以本阶段不会伪造 `sensor` 或当前 geometry。此类小时记录会被明确跳过并汇总 ID/行数，等待团队/DS 决定如何补充历史 sensor master。

ID 14、37、47、181 的有效原始小时观测不会因迁移备注而在本阶段删除。它们的 Local baseline 限制（37 从 2024-08-12 开始；47/181 暂停 Local Condition）应在下一阶段建立 baseline 时应用。`source_location_text` 只保留来源文本，不能证明旧记录发生在今天的 current geometry。

## 5. Dry run 与真实导入

先用一个很小的范围检查 live 字段和数据质量：

```powershell
$env:DATABASE_URL='postgresql+psycopg://epic1:epic1@localhost:5432/epic1'
.\backend\.venv\Scripts\python.exe .\scripts\import_hourly_counts.py --dry-run --start-date 2025-01-04 --end-date 2025-01-04
```

Dry run 会读取真实 CSV、保留 0、验证日期/小时/count，并只读检查 unknown IDs，不写数据库。

真实导入与重复验证：

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\import_hourly_counts.py --start-date 2025-01-04 --end-date 2025-01-04
.\backend\.venv\Scripts\python.exe .\scripts\import_hourly_counts.py --start-date 2025-01-04 --end-date 2025-01-04
```

## 6. 数据库只读验证

```powershell
docker exec epic1-postgis psql -U epic1 -d epic1 -c "SELECT COUNT(*), COUNT(*) FILTER (WHERE total_of_directions = 0), MIN(sensing_date), MAX(sensing_date) FROM pedestrian_hourly_count WHERE sensing_date BETWEEN DATE '2025-01-04' AND DATE '2025-01-04';"
docker exec epic1-postgis psql -U epic1 -d epic1 -c "SELECT COUNT(*) - COUNT(DISTINCT (location_id, sensing_date, hour_day)) AS duplicate_keys FROM pedestrian_hourly_count;"
```

这是本地开发数据导入，不是云部署。不要提交 `.env`，也不要把 `DATABASE_URL` 输出到日志或前端。
