# CalmWay Phase 3E：路线采样点人群评估

## 范围

Phase 3D 只负责把完整 Mapbox `LineString` 按累计距离转换为有序 `RouteSample`。Phase 3E 对每个 sample 调用已经完成的 Phase 2D `SpatialCrowdService`，返回有序的 sample-level 人群结果。

```text
现有 GeoJSON LineString
  -> RouteSamplingService（Phase 3D）
  -> RouteSample[]
  -> SpatialCrowdService.evaluate（Phase 2D）
  -> RouteSampleCrowdResult[]
```

本阶段到 sample-level 结果为止，不计算路线平均值、P75、最大值、覆盖百分比、路线等级、用户 tolerance、排名或推荐。这些属于 Phase 4。

## 为什么使用进程内服务组合

`RouteCrowdEvaluationService` 直接组合 Python 服务，不通过 HTTP 调用 CalmWay 自己的 `/api/v1/crowd/point`。因此不会产生 localhost HTTP N+1，也不会复制 FastAPI 参数/错误转换逻辑。

每个 sample 仍由 Phase 2D 的现有实现负责：

- PostGIS `ST_DWithin` / `ST_Distance`；
- 250 m core 与 300 m maximum support；
- 只使用有效 Active Outdoor 数值；
- 标准化 `1 / max(distance, 1 m)` 权重；
- Network Crowd Exposure 与独立 Local Condition；
- 当前 materialisation 的 window 和 uncertainty 语义。

Phase 3E 不重新实现任何空间数学。

## 不可变结果结构

```text
RouteSampleCrowdResult(
  sample: RouteSample,
  crowd: PointCrowdEstimate
)

RouteCrowdEvaluation(
  route_id,
  route_length_meters,
  sampling_interval_meters,
  sample_results
)
```

通过组合现有模型，每个 sample 保留 Phase 3D 的 index、累计距离和坐标，并原样保留 Phase 2D 的 `PointCrowdEstimate`，包括 exposure、point crowd level、Local Condition、coverage、sensor support、最近有效传感器距离、support radius、source window、updated time、reason 和 contributions。

`sample_count` 只是 `sample_results` 的长度。服务没有路线级 crowd metric。

## SUPPORTED、LIMITED 与 NO_DATA

- 最近有效 contributor `<=250 m`：原样返回 `SUPPORTED`。
- 最近有效 contributor `>250 m` 且 `<=300 m`：原样返回 `LIMITED`，不会升级为 `SUPPORTED` 或降级为 `NO_DATA`。
- 300 m 内没有有效数值 contributor：原样返回 `NO_DATA`。

`NO_DATA` 是有效 domain 结果，不是 exception。它的 Crowd Exposure、Crowd Level 以及适用的 Local Condition 字段保持 `NULL`。`AMBIGUOUS_NO_RECORD` 也不会贡献数值，绝不会变成 0、`VERY_LOW` 或 `LOW`。

无效 geometry / sampling error、数据库错误、PostGIS 查询错误和 materialisation consistency error 会继续抛出受控错误，不会伪装成 `NO_DATA`。

## 当前 materialisation

路线评估只读取现有 `current_sensor_activity`。它不会调用 City API，也不会自动运行 `refresh_current_activity.py`。刷新当前数据仍然是独立运维操作。

如果当前 City source window 没有有效 Outdoor 数值，一条真实路线的全部 sample 都可能是 `NO_DATA`。这是诚实且成功的结果，不需要修改数据库或注入 fallback LOW。

## 单元测试

普通 mocked tests 不需要 PostgreSQL：

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_route_crowd_evaluation_service.py
```

它们验证 sampling 只调用一次、每个 sample 只评估一次、顺序/距离/坐标不变、三种 coverage 与数值/null/Local Condition 原样传播，以及 sampling/database error 不会变成 `NO_DATA`。

## Rollback-only PostGIS integration

先配置 `DATABASE_URL`，再显式打开 gate：

```powershell
$env:RUN_ROUTE_CROWD_INTEGRATION="1"
.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_route_crowd_postgis_integration.py
Remove-Item Env:RUN_ROUTE_CROWD_INTEGRATION
```

测试在远离真实传感器的控制区域插入两个临时 Active Outdoor contributor，生成包含 `SUPPORTED`、`LIMITED` 和 `NO_DATA` 的路线，并在同一 SQLAlchemy connection 内复用 Phase 2D repository。测试在 `finally` 中 rollback，然后验证核心表行数、current window 和临时 ID 均恢复。

## 真实当前状态验证

使用 Phase 3D 已存储的 Flinders Street Station 到 Melbourne Central fixture：

```powershell
.\.venv\Scripts\python.exe .\scripts\evaluate_route_crowd.py
```

可选逐 sample 输出：

```powershell
.\.venv\Scripts\python.exe .\scripts\evaluate_route_crowd.py --details
```

脚本只打印 coverage 数量、numeric/unavailable 数量和首尾 sample，不计算路线 crowd 分数。如果 25 个 sample 全部为 `NO_DATA`，脚本仍输出 `Status: OK`。

Phase 4 才会依据权威 DS/ranking specification 聚合这些 sample-level 结果。
