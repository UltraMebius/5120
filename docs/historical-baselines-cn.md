# CalmWay 历史 Baseline 构建指南（Phase 2B）

## 1. 数据流程与窗口

Phase 2B 只实现：

```text
pedestrian_hourly_count
  -> 训练窗口与资格规则
  -> sensor_hour_daytype_baseline
  -> network_hour_daytype_baseline
```

冻结训练窗口是 `2024-08-10` 至 `2026-02-07`，含首尾两天。起点是后端直接可用的 City live hourly source 起点；不补另一份 archive 中的 8 月 8、9 日。`2026-02-08` 及之后是 holdout，不参与构建。

`pedestrian_hourly_count` 是可追踪的原始小时事实；两个 baseline 表是可以重新计算的派生数据。构建 baseline 不删除或修改原始小时表。

## 2. Local 与 Network 的区别

Local baseline 按以下键分组：

```text
location_id × hour_day × day_type
```

它表示某个位置在同一小时、同一工作日类型下的历史分布。

Network baseline 按以下键分组：

```text
hour_day × day_type
```

它直接汇总合格 sensor 的原始小时观察，不是对各 sensor percentile 再求平均。它为未来没有可靠 Local baseline 的位置提供 Network fallback。Phase 2B 只准备数据，不计算 Crowd Level 或 Local Condition。

## 3. 模型资格与特殊 ID

历史模型只使用能与当前权威位置表对齐、`status = A`、`location_type = Outdoor` 的 sensor。完整窗口实际有 100 个这样的 sensor、1,182,041 条观察。当前 34 个 Indoor sensor 在该训练窗口中没有原始小时记录；即使将来出现 Indoor 原始行，也不会为了增加样本量而放入户外步行模型。

特殊规则：

- Sensor 14：Local 使用完整冻结窗口；已知 2019 年迁移早于训练数据；
- Sensor 37：Local 只使用 `2024-08-12` 起的数据；8 月 10、11 日排除；Network 可保留这些有效 count；
- Sensor 47、181：不发布 Local baseline；它们的有效 count 仍进入 Network；
- source ID 28、78：团队已知无法对齐，Local/Network 均排除；
- source ID 65：完整窗口 dry-run 新发现同样不在当前 master，按相同安全规则报告并排除；
- 不为任何 unresolved ID 伪造 sensor、位置或历史 geometry。

## 4. 统计方法

对每个 Local 或 Network 分组，0 也是合法观察，不能过滤或改成 `NULL`。写入 schema 已定义的全部字段：

```text
observation_count
mean_count
median_count
p10, p20, p25, p40, p50, p60, p75, p80, p90, p95
baseline_start_date, baseline_end_date
```

均值使用 `AVG`。中位数与所有分位数使用 PostgreSQL `PERCENTILE_CONT`，即排序后按 `(n - 1) × p` 做连续线性插值；`median_count = p50`。`baseline_start_date` 和 `baseline_end_date` 是该分组实际参与观察的最早、最晚日期。

DS handoff 没有定义 minimum sample threshold，因此没有擅自增加阈值。每个实际存在的非空分组都会写入，并保留 `observation_count` 供审计。

未来的历史 percentile 定义仍是 handoff 的经验 CDF：

```text
100 × count(reference value <= x) / count(reference value)
```

Phase 2B 不实现未来的当前小时比较或 crowd band。

## 5. Dry-run 与真实构建

```powershell
$env:DATABASE_URL='postgresql+psycopg://epic1:epic1@localhost:5432/epic1'
```

只读检查完整性、模型资格、zero 和特殊规则：

```powershell
.\.venv\Scripts\python.exe .\scripts\build_historical_baselines.py --dry-run
```

真实构建：

```powershell
.\.venv\Scripts\python.exe .\scripts\build_historical_baselines.py
```

真实构建在一个 transaction 中只执行：清空两个派生 baseline 表，再从原始小时事实重新插入。任一 SQL 失败时，两个表一起 rollback。不会 truncate 或删除 `sensor`、`sensor_location_current`、`pedestrian_hourly_count`。

同一份原始数据重复运行会得到相同主键、row count 和统计值；只有审计字段 `calculated_at` 会反映新的构建时间。脚本输出忽略该时间字段的逻辑 checksum，方便检查幂等性。

## 6. 数据库验证

```powershell
docker exec epic1-postgis psql -U epic1 -d epic1 -c "SELECT COUNT(*) AS local_rows, COUNT(DISTINCT location_id) AS local_sensors FROM sensor_hour_daytype_baseline;"
docker exec epic1-postgis psql -U epic1 -d epic1 -c "SELECT COUNT(*) AS network_rows, COUNT(DISTINCT hour_day) AS hours, COUNT(DISTINCT day_type) AS day_types, SUM(observation_count) AS contributing_rows FROM network_hour_daytype_baseline;"
docker exec epic1-postgis psql -U epic1 -d epic1 -c "SELECT location_id, COUNT(*), MIN(baseline_start_date), MAX(baseline_end_date) FROM sensor_hour_daytype_baseline WHERE location_id IN (14,37,47,181,28,65,78) GROUP BY location_id ORDER BY location_id;"
docker exec epic1-postgis psql -U epic1 -d epic1 -c "SELECT COUNT(*) AS invalid_stats FROM sensor_hour_daytype_baseline WHERE NOT (p10<=p20 AND p20<=p25 AND p25<=p40 AND p40<=p50 AND p50<=p60 AND p60<=p75 AND p75<=p80 AND p80<=p90 AND p90<=p95);"
```

预期 Network 有 24 × 2 = 48 个键。47、181 不应出现在 Local 表；14、37 应存在，且 37 的 `baseline_start_date` 不早于 `2024-08-12`。

## 7. 本阶段边界

本阶段没有导入 minute 数据，没有写 `current_sensor_activity` 或 `spatial_activity_cache`，没有实现 15 分钟活动、Crowd Level、空间加权、Mapbox、路线、导航或前端功能。
