# Phase 2C 当前传感器活动说明

## 数据源与用途

Phase 2C 使用 City of Melbourne 官方数据集 `pedestrian-counting-system-past-hour-counts-per-minute`。它提供每分钟、按方向统计的行人计数，城市端大约每 15 分钟刷新。CalmWay 不下载接口当前暴露的全部积压记录；每次只通过 Records API 的服务端 `where` 条件和稳定分页读取“上一个完整小时开始”到“当前完整 15 分钟窗口结束”的数据。

实际接口字段为：`location_id`、`sensing_datetime`、`sensing_date`、`sensing_time`、`direction_1`、`direction_2`、`total_of_directions`。时间按 `Australia/Melbourne` 解释，不能写死 UTC+10，因为墨尔本有夏令时。

## 缺失、零、重复与冲突

City 说明无行人时某分钟可能没有记录，因此“没有行”不能证明计数为 0。只有源数据明确提供 `total_of_directions = 0` 时才保留数值零。某传感器在完整窗口内排除冲突后仍没有有效行时：

```text
data_state = AMBIGUOUS_NO_RECORD
current_15m_count = NULL
current_15m_network_percentile = NULL
```

它不会被标成 LOW，也不参加 Network 排名。

`pedestrian_minute_observation_raw` 是不可变的来源证据层。程序用完整规范化载荷的 SHA-256 去除完全相同的重复轮询结果。同一 `location_id + sensing_datetime` 若出现不同载荷，两行都保留为冲突证据，但整个逻辑时点不参与聚合；绝不相加、平均或任取一条。handoff 没有给出 raw 保留期限，所以本阶段不发明删除策略，也不建立无限归档承诺；保留策略明确延期。

## 当前 15 分钟窗口

严格规则为：

```text
window_end = floor(当前墨尔本时间到 15 分钟边界)
window_start = window_end - 15 个实际分钟
范围 = [window_start, window_end)
```

边界右侧不包含。活动传感器有至少一条未冲突有效行时，`current_15m_count` 为窗口内有效 `total_of_directions` 的总和。

`current_sensor_activity` 是派生的最新传感器状态表。每次成功计算都在一个事务内替换这张表，不修改 raw、历史小时、baseline、传感器几何或空间表。同一 source snapshot 与同一 `--as-of` 的逻辑输出一致；`calculated_at` 只记录实际构建时间。

## Freshness 与状态

不按“某传感器 N 分钟无行”判断故障。`STALE` 只表示整个来源/缓存的运营 freshness 失败。`SOURCE_CACHE_STALE_AFTER_MINUTES` 为空时不虚构 SLA：命令仍报告最新来源时间和年龄，但不会仅凭年龄标记 STALE。若来源最新时间不存在，或部署方配置了 SLA 且已超时，活动 Outdoor 传感器标为 `STALE`，当前数值与分数保持 `NULL`。

## 两种互不混合的比较

当前 Network Crowd Exposure 仅对当前 `status=A` 且 `location_type=Outdoor`、状态为 `OK` 的传感器计算：

```text
100 * count(当前有效传感器 15m count <= 本传感器 count)
    / count(当前有效传感器)
```

该值同时写入 `current_15m_network_percentile` 和 `current_crowd_exposure_score`，并按 25/50/75/90 分成 `VERY_LOW`、`LOW`、`MODERATE`、`HIGH`、`VERY_HIGH`。

只有来源区间能重建上一个完整时钟小时的全部 60 个分钟时点时，才把该小时的有效 minute 行求和。然后直接读取冻结的 `pedestrian_hourly_count` 参考分布，以精确经验 CDF 计算：

```text
HistoricalPercentile = 100 * count(reference <= current_1h_count)
                             / count(reference)
```

Network history 使用相同 `hour_day + day_type` 的合资格监测观测；Local history 还要求相同 `location_id`，并继续遵守 Phase 2B 的迁移规则。程序不会用 P10/P20 等摘要近似 CDF，也不会把 Local 与 Network 取 MAX 或平均。

传感器 47、181 的当前位置和当前 minute 活动仍有效，也参加当前 Network 分数；只是 Local history 保持 `NULL`。14 使用完整批准历史，37 的 Local history 从 2024-08-12 开始。

raw 存储与建模资格是两件事：已知 Indoor 或 inactive 来源行可以进入 raw 证据层，但不会参与当前人流建模，其当前派生状态为 `NO_DATA`。

## 团队运行命令

先确认 Docker 中的 `epic1-postgis` 正在运行，而且忽略提交的 `backend/.env` 或进程环境已配置 `DATABASE_URL`。

只读预览：

```powershell
.\.venv\Scripts\python.exe .\scripts\refresh_current_activity.py --dry-run
```

真实刷新：

```powershell
.\.venv\Scripts\python.exe .\scripts\refresh_current_activity.py
```

固定相同窗口以验证幂等性（示例时间必须替换为需要验证的、带 offset 的时间）：

```powershell
.\.venv\Scripts\python.exe .\scripts\refresh_current_activity.py --as-of 2026-08-10T18:29:00+10:00
.\.venv\Scripts\python.exe .\scripts\refresh_current_activity.py --as-of 2026-08-10T18:29:00+10:00
```

数据库集成审计：

```powershell
$env:RUN_CURRENT_ACTIVITY_INTEGRATION='1'
.\.venv\Scripts\python.exe -m pytest tests\integration\test_current_activity_database_integration.py -q
Remove-Item Env:RUN_CURRENT_ACTIVITY_INTEGRATION
```

显式实时 City 集成（会写官方当前数据）：

```powershell
$env:RUN_CITY_MINUTE_INTEGRATION='1'
.\.venv\Scripts\python.exe -m pytest tests\integration\test_city_minute_live_integration.py -q
Remove-Item Env:RUN_CITY_MINUTE_INTEGRATION
```

也可在 `psql` 中检查：raw 和 current 均有行、`payload_hash` 无重复、冲突组与 view 一致、`location_id` 无孤儿、计数非负、15 分钟长度正确、AMBIGUOUS/STALE 的当前数值为 NULL、47/181 的 Local 值为 NULL、Indoor 为 NO_DATA，以及历史 baseline 行数和校验和没有变化。

## 本阶段边界

这是本机手动刷新能力，不是云部署，也没有 cron、Celery、Redis 或后台 scheduler。本阶段没有写入 `spatial_activity_cache`，没有 250/300m 空间插值、Mapbox、路线生成/排名、前端连接、预测或 AI 模型。Phase 2C 到传感器级 current activity 即停止。
