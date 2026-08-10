# CalmWay 历史小时数据导入指南

本项目使用 City of Melbourne 官方数据集：

```text
pedestrian-counting-system-monthly-counts-per-hour
```

导入目标是权威原始表 `pedestrian_hourly_count`。该表与 Local/Network baseline 分开，重复导入按 `(location_id, sensing_date, hour_day)` 更新，不会制造重复记录。

## 冻结训练窗口

Phase 2B 已把生产训练窗口固定为：

```text
2024-08-10 至 2026-02-07（含首尾两天）
```

`2024-08-10` 是后端直接可用的官方 live hourly source 起点。本项目不从另一份 archive 补 `2024-08-08` 或 `2024-08-09`。`2026-02-08` 之后属于 holdout，不能进入 baseline。

## 数据语义

- `total_of_directions = 0` 是真实观察值，必须保留；
- 缺失、负数或无法解析的 count 不会被改成 0；
- `day_type` 按 Melbourne 日历日期生成：周一至周五为 `Weekday`，周六、周日为 `Weekend`；
- `source_id` 只用于来源追踪，不是数据库主键；
- 导入器使用服务端日期过滤、流式 CSV 和有限大小的数据库批次，不把完整数据集载入内存。

历史 source ID 28、78 无法与当前权威 sensor master 对齐。完整窗口 dry-run 还发现 ID 65 同样不在当前 master。导入器会报告并跳过这些记录，不会伪造 sensor、位置或 geometry。

## 导入命令

先设置本地数据库连接：

```powershell
$env:DATABASE_URL='postgresql+psycopg://epic1:epic1@localhost:5432/epic1'
```

完整窗口 dry-run（只读，不写数据库）：

```powershell
.\.venv\Scripts\python.exe .\scripts\import_hourly_counts.py --start-date 2024-08-10 --end-date 2026-02-07 --dry-run
```

官方服务器可能会关闭持续数分钟的单个 CSV 响应。真实导入建议使用可恢复的较短日期段；每一段仍调用同一个权威导入器：

```powershell
$ranges = @(
  @('2024-08-10','2024-10-31'),
  @('2024-11-01','2024-12-31'),
  @('2025-01-01','2025-02-28'),
  @('2025-03-01','2025-04-30'),
  @('2025-05-01','2025-06-30'),
  @('2025-07-01','2025-08-31'),
  @('2025-09-01','2025-10-31'),
  @('2025-11-01','2025-12-31'),
  @('2026-01-01','2026-02-07')
)
foreach ($range in $ranges) {
  .\.venv\Scripts\python.exe .\scripts\import_hourly_counts.py `
    --start-date $range[0] --end-date $range[1] --batch-size 5000
  if ($LASTEXITCODE -ne 0) { throw "Import failed: $($range[0]) to $($range[1])" }
}
```

中断后可以重新运行同一段。已提交批次会安全更新，未完成部分会继续插入；不要 truncate `pedestrian_hourly_count`。

## 只读验证

```powershell
docker exec epic1-postgis psql -U epic1 -d epic1 -c "SELECT COUNT(*) AS rows, COUNT(DISTINCT (location_id,sensing_date,hour_day)) AS distinct_keys, COUNT(*) FILTER (WHERE total_of_directions=0) AS zeros, MIN(sensing_date), MAX(sensing_date) FROM pedestrian_hourly_count WHERE sensing_date BETWEEN DATE '2024-08-10' AND DATE '2026-02-07';"
```

本地 `.env` 不应提交，也不要把数据库密码或 token 放入前端。
