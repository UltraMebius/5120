# CalmWay Phase 3D：均匀路线采样

## 目标与边界

Phase 3D 把 Phase 3B 已取得的完整 Mapbox GeoJSON `LineString` 转换为按路线累计距离排序的采样点。采样完全在后端内存中完成，不请求 Mapbox、不访问数据库，也不调用 `SpatialCrowdService` 或 `/api/v1/crowd/point`。

Phase 3D 到生成采样点为止。Phase 3E 才会把这些点交给人群空间评估。

## 为什么不能直接使用 Mapbox 顶点

Mapbox LineString 顶点描述路线形状，但顶点之间的距离不均匀。弯道可能有许多密集顶点，直线路段可能只有少量相距较远的顶点。如果把原始顶点直接当作人群采样点，弯道会被过度代表，长直路段会被低估。

因此，Phase 3D 先测量整条几何的累计距离，再按固定距离生成新点。Mapbox LineString 始终是权威路线；采样点不会重新贴路，也不会吸附到传感器。

## 配置

采样间隔只读取现有 `SETTINGS.route.sample_interval_m`，其环境变量为：

```text
ROUTE_SAMPLE_INTERVAL_M=50
```

当前实际值为 **50 米**，与 `.env.example` 和 `handoff/epic1_backend_handoff_v3/04_IMPLEMENTATION_CONFIG.yaml` 一致。没有新增第二个采样配置。

## 距离计算

每个相邻坐标段使用 Haversine 大圆距离，地球平均半径为 `6,371,008.8 m`：

```text
a = sin²(Δφ/2) + cos(φ1) × cos(φ2) × sin²(Δλ/2)
c = 2 × atan2(√a, √(1-a))
distance = 6,371,008.8 × c
```

输入坐标顺序始终是 `[longitude, latitude]`。经纬度只在计算中转换为弧度，不会把角度直接当作米。

## 累计距离与插值

服务先计算每一段的长度和起止累计距离，然后生成目标距离：

```text
0, interval, 2 × interval, 3 × interval, ...
```

对于每个内部目标距离，服务找到包含它的 LineString 段，并按该目标在段内的距离比例，对 longitude 和 latitude 做线性插值。该方法适合本项目的短距离墨尔本步行段。

输出为不可变、有序结构：

```text
RouteSample(
  index,
  distance_along_route_meters,
  longitude,
  latitude
)
```

`index` 从 0 连续递增，方向始终从 LineString 第一个坐标到最后一个坐标。

## 起点、终点和边界情况

- 第一条 sample 直接复制第一个 LineString 坐标，累计距离为 0。
- 最后一条 sample 直接复制最后一个 LineString 坐标，累计距离为测得的总路线长度。
- 如果总长度小于间隔，只返回起点和终点。
- 如果总长度恰好是 `N × interval`，最后一个计划采样点就是终点，不会再追加重复终点。
- 连续重复坐标形成的零长度段会被安全跳过，不参与除法或插值。
- 如果所有段都是零长度，服务抛出受控 `DegenerateRouteGeometryError`，不会生成大量相同点。

## Geometry 验证

输入必须满足：

- `type == "LineString"`；
- 至少两个坐标；
- 每个坐标恰好包含可用的 longitude 和 latitude；
- 数值必须有限；
- longitude 位于 `-180..180`；
- latitude 位于 `-90..90`。

## 本地验证

运行 Phase 3D 单元测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_route_sampling_service.py
```

运行完整后端测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

使用存储的 Flinders Street Station 到 Melbourne Central 形状/尺度 fixture：

```powershell
.\.venv\Scripts\python.exe .\scripts\sample_route_geometry.py
```

脚本只打印总长度、配置间隔、sample 数量、首尾 sample 和简洁间距摘要，不输出所有采样点。
