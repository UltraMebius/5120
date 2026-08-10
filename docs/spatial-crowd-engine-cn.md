# Phase 2D 空间点人流引擎

## 为什么需要空间引擎

Phase 2C 的结果属于传感器坐标；之后的步行路线采样点通常不与传感器重合。Phase 2D 将 `sensor_location_current` 与 `current_sensor_activity` 连接，把附近传感器已经标准化的当前 Network percentile 转换为一个查询点的 Crowd Exposure。它不调用 City API，也不聚合相隔地点的原始人数。

传感器级结果回答“这个传感器当前如何”；点级结果回答“这个经纬度附近有多少可信的当前传感器支持，以及加权后的相对人流是多少”。

## PostGIS 查询

输入使用 WGS84，几何顺序永远是 `X=longitude`、`Y=latitude`。服务验证 longitude 在 `[-180,180]`、latitude 在 `[-90,90]`，但 handoff 没有定义 CBD polygon，所以不虚构额外边界。

数据库对现有 `geography(Point,4326)` 使用：

- `ST_DWithin`：利用 GiST 索引查找 300 m 内传感器；
- `ST_Distance`：返回准确的米距离；
- geography KNN 排序：只为 `NO_DATA` 提供最近有效传感器距离说明，不让 300 m 外传感器参与分数。

没有在 Python 中把经纬度当平面距离，也没有用“度约等于公里”的近似。

## 权威空间支持规则

唯一有效贡献者是：

```text
location_type = Outdoor
status = A
data_state = OK
current_15m_network_percentile 非 NULL
distance <= 300 m
```

没有“至少 3 个传感器”规则，也没有 nearest-5。所有符合条件且在 300 m 内的传感器都贡献；core radius 只决定 coverage 状态，不是两阶段扩圈：

```text
最近有效贡献者 <= 250 m       -> SUPPORTED
250 m < 最近距离 <= 300 m     -> LIMITED
最近距离 > 300 m 或没有有效值 -> NO_DATA
```

不会继续扩大半径直到找到传感器。`AMBIGUOUS_NO_RECORD`、`NO_DATA`、`CONFLICTED`、`STALE`、Indoor 和 inactive 都不能作为数值零贡献。附近即使有很多 ambiguous 传感器，点结果仍为 `NO_DATA`，分数和 Crowd Level 为 `NULL`，绝不会变成 LOW。

## 距离权重与分类

最终 V1B Network-target 公式为：

```text
raw_weight_i = 1 / max(distance_i, 1 m)^1
weight_i = raw_weight_i / sum(raw_weight)
PointCrowdExposure = sum(weight_i * current_15m_network_percentile_i)
```

`power=1`，distance floor 为 `1 m`，所以查询点正好位于传感器上也不会除零。点 Crowd Level 复用 Phase 2C 的 25/50/75/90 分类函数。

若贡献者存在 `current_1h_local_historical_percentile`，Local Condition 使用同样的 `1/d` 形式，但只在 Local 有效子集内重新归一化；它与当前 Network Crowd Exposure 始终分开。

## API 与命令

handoff 已定义的内部 API 已实现：

```text
GET /api/v1/crowd/point?lat=-37.81&lon=144.96
```

数据库不可用只会让该请求返回 503，不影响 FastAPI 启动或 `/health`。

从仓库根目录手动查询：

```powershell
$env:DATABASE_URL='postgresql+psycopg://epic1:epic1@localhost:5432/epic1'
.\.venv\Scripts\python.exe .\scripts\evaluate_crowd_point.py --longitude 144.96 --latitude -37.81
.\.venv\Scripts\python.exe .\scripts\evaluate_crowd_point.py --longitude 144.96 --latitude -37.81 --debug
```

输出包含 coverage、半径内传感器数、实际贡献数、最近有效距离、加权分数、分类、当前窗口和 materialisation 时间。Debug 只额外显示贡献者，不暴露所有 raw 数据。

运行普通和 PostGIS 集成测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_spatial_crowd_service.py tests\test_spatial_repository.py tests\test_spatial_api.py -q
$env:RUN_SPATIAL_INTEGRATION='1'
.\.venv\Scripts\python.exe -m pytest tests\integration\test_spatial_postgis_integration.py -q
Remove-Item Env:RUN_SPATIAL_INTEGRATION
```

集成测试在一个事务内建立已知 0 m/100 m 数值传感器、Indoor 和 ambiguous 对照，验证后 rollback，不改变当前生产形状数据。

## Cache 与当前 live ambiguity

`spatial_activity_cache` 的 schema 已存在，但 handoff 没有冻结坐标精度、逻辑唯一键或缓存单元。为了避免随机坐标无限增长和旧窗口误用，Phase 2D 不写该表；点服务保持无状态、只读。`supportingScoreStddev` 同样没有定义总体/样本/加权公式，因此正常响应保持 nullable，而不发明数学规则。

当前 live materialisation 的 100 个 Outdoor 传感器都是 `AMBIGUOUS_NO_RECORD`，34 个 Indoor 是 `NO_DATA`。因此真实点查询现在合理返回 `NO_DATA`；确定性数值行为由 fixture、unit tests 和 rollback-only PostGIS integration 验证，不篡改当前表来制造 LOW/HIGH。

## 阶段边界

Phase 2D 只完成点级引擎。没有 Mapbox、geocoding、Directions、路线 LineString、路线采样、路线聚合/排名、前端连接、预测或 AI。Phase 3 才会把这个点 evaluator 用于真实步行路线采样。
