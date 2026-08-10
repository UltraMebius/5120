# CalmWay Phase 4 路线人流聚合与排序决策

## 文档性质

本文记录 CalmWay Phase 4 经项目团队批准的 MVP 实施决策，用来补充 DS/backend handoff 中标记为 `provisional` 或 `requires_user_validation` 的路线级规则。

这些规则是产品与工程决策，不是经数据科学实验或代表性用户研究验证的结论。原始 handoff 快照保持不变；未来完成正式验证后，才可将排序状态标记为 `VALIDATED`。

## 路线样本与覆盖率

- 样本只有在 `coverageStatus` 为 `SUPPORTED` 或 `LIMITED`，且 `crowdExposureScore` 为有限数值时，才是可用数值样本。
- MVP 中 `SUPPORTED` 与 `LIMITED` 等权参与路线聚合；两类占比仍分别保留用于诊断。
- `NO_DATA` 不参与数值计算，绝不转换为 `0`、`VERY_LOW` 或 `LOW`。
- `numericSampleCount` 是上述可用数值样本数。
- `totalSampleCount` 是 Phase 3D 产生的全部路线样本数。
- `dataCoveragePct = 100 * numericSampleCount / totalSampleCount`。
- `noDataPct = 100 * NO_DATA 样本数 / totalSampleCount`。
- `supportedPct` 与 `limitedPct` 分别使用各自状态样本数除以 `totalSampleCount`。

## 最低覆盖率与数据不足

- 配置项 `MINIMUM_ROUTE_CROWD_COVERAGE_PCT` 的 MVP 默认值为 `55`。
- `dataCoveragePct >= 55` 时路线可进行人流评估；恰好 `55%` 视为足够。
- `dataCoveragePct < 55` 时状态为 `INSUFFICIENT_DATA`。
- 数据不足的路线继续显示 Mapbox 距离、时间和几何，不产生路线人流分数或虚假推荐。

## 路线人流聚合

可评估路线的 `routeCrowdScore` 是全部可用数值样本 `crowdExposureScore` 的连续插值 P75。所有可用样本在 MVP 中等权；不做路径分段加权。

将数值升序排列为 `x[0..n-1]`：

```text
position = (n - 1) * 0.75
lower = floor(position)
upper = ceil(position)

lower == upper:
    P75 = x[lower]

otherwise:
    fraction = position - lower
    P75 = x[lower] + fraction * (x[upper] - x[lower])
```

该方法与 `PERCENTILE_CONT` 原理一致，不使用 nearest-rank。`routeMaximumExposure` 是可用数值样本的最大值。

路线内部类别复用现有 Network 五级分类器：`VERY_LOW / LOW / MODERATE / HIGH / VERY_HIGH`。路线分数为 P75，不创建新的数值阈值。

产品展示映射为：

- `VERY_LOW` 或 `LOW` → `LOW`
- `MODERATE` → `MEDIUM`
- `HIGH` 或 `VERY_HIGH` → `HIGH`

展示等级与用户选择的容忍度等级是两个不同概念。

## 用户容忍度与偏好状态

继续复用现有配置：

| UI 容忍度 | 内部偏好 | 最大偏好分数 |
|---|---|---:|
| LOW | `AVOID_BUSY` | 50 |
| MEDIUM | `PREFER_QUIETER` | 75 |
| HIGH | `FLEXIBLE` | 90 |

对于可评估路线：

- `abovePreferencePct = 100 * count(score > threshold) / numericSampleCount`；`NO_DATA` 不进入分母。
- 样本等于阈值时仍在偏好范围内。
- `routeCrowdScore <= threshold` → `WITHIN_PREFERENCE`。
- `routeCrowdScore > threshold` → `ABOVE_PREFERENCE`。

覆盖率不足时偏好状态为 `INSUFFICIENT_DATA`。偏好是软约束，不过滤路线。

## 排序与推荐

覆盖率足够的路线按以下字段升序进行字典序排序：

1. `noDataPct`
2. `abovePreferencePct`
3. `routeCrowdScore`
4. `routeMaximumExposure`
5. `durationSeconds`
6. Mapbox `routeIndex`

不使用加权综合分数，不使用随机排序。`routeIndex` 是最终确定性 tie-break。

数据不足路线排在所有可评估路线之后，并保持 `routeIndex` 顺序。

如果有可评估路线，即使全部超过用户偏好，也继续按上述规则排序，并推荐第一条可评估路线。若所有路线数据不足，则 `recommendedRouteId = null`，不得以最短路线冒充 CalmWay 推荐。

## 排序状态

- `NOT_EVALUATED`：尚未尝试路线人流排序。
- `PROVISIONAL`：已使用本文项目批准但尚未外部验证的 MVP 策略完成排序。
- `INSUFFICIENT_DATA`：已尝试评估，但没有任何路线达到 55% 可用覆盖率。
- `VALIDATED`：保留给未来完成正式验证后的策略，Phase 4 不使用。

当状态为 `PROVISIONAL` 时，`recommendedRouteId` 是排序后第一条覆盖率足够路线的 ID；状态为 `INSUFFICIENT_DATA` 时必须为 `null`。

## 前端职责

- 后端拥有聚合、偏好判断、排序与推荐逻辑。
- Route Options 按后端返回顺序展示，不在 React 中重新排序。
- 只有后端提供真实 `recommendedRouteId` 时才显示 CalmWay recommendation。
- 数据不足时显示诚实的 unavailable/insufficient 状态，不显示虚假 LOW/HIGH。
- 超过偏好时继续显示路线，并明确提示，例如 “Above your LOW preference”。

## API 与服务组合

现有 `POST /api/v1/routes/walking` 保持唯一的 Route Search 公共流程：

```text
React Route Search
→ WalkingRoutingService
→ Mapbox walking candidates
→ RouteCrowdEvaluationService
→ RouteSamplingService + SpatialCrowdService
→ RouteCrowdRankingService
→ 后端排序后的 WalkingRouteOption[]
→ Journey Context / Route Options
```

响应继续包含 Mapbox 路线字段，并增加覆盖率、P75、最大值、偏好状态、内部/展示等级、rank 与 `isRecommended`。顶层增加本文定义的完整 `rankingStatus` 语义。前端保存 `recommendedRouteId`，不自行计算推荐。

所有路线在同一请求内必须来自一个 current crowd materialisation。若样本跨越不同窗口或 materialisation，后端将其视为一致性错误，而不是伪装成 `INSUFFICIENT_DATA`。路线评估不会触发 current activity refresh。

## 受控测试

纯单元/API 测试：

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests/test_route_crowd_ranking_service.py `
  tests/test_routes_api.py -q
```

回滚式 PostGIS 全链路测试：

```powershell
$env:RUN_ROUTE_RANKING_INTEGRATION='1'
.\.venv\Scripts\python.exe -m pytest `
  tests/integration/test_route_crowd_postgis_integration.py -q
Remove-Item Env:RUN_ROUTE_RANKING_INTEGRATION
```

该测试在事务中插入受控 `current_sensor_activity`，验证 Mapbox-like LineString → Phase 3D → Phase 3E → Phase 4 → 偏好 → 推荐，然后回滚，并比较前后数据库完整性。

## 真实当前状态验证

使用本地当前 materialisation 和真实 Mapbox walking candidates：

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_route_ranking.py `
  --preference PREFER_QUIETER
```

脚本只输出路线 ID、距离、时间、覆盖率、路线人流结果、偏好状态、rank 与推荐标志；不会打印 token，不会刷新 City 数据，也不会写数据库。

如果真实路线仍为全部 `NO_DATA`，正确结果是：

```text
rankingStatus = INSUFFICIENT_DATA
recommendedRouteId = null
routeCrowdScore = null
routeCrowdLevel = null
```

这是一条有效但无法进行当前人流排序的 Mapbox 路线，不是系统失败。数据库、Mapbox 或应用错误继续走错误路径，不转换为数据不足。

## 为什么 NO_DATA 永远不是 LOW

`LOW` 表示一个已观测、已标准化并落在较低 Network percentile 范围内的数值结论；`NO_DATA` 表示缺少有效空间支持。将后者转换为零或 LOW 会产生虚假安心，因此它只影响覆盖率，并在覆盖不足时阻止推荐。

## Phase 4 范围边界

本阶段不实现 GPS、导航进度、人流警报、重新规划、预测、AI/ML、彩色路线分段、后台队列或路线结果持久化。路线评估保持请求级，不新增数据库 schema。

后续工作仍包括导航期 GPS/进度、实时警报与重新规划、正式路线排序用户验证以及部署。只有完成预定验证后，才可使用 `VALIDATED`。
