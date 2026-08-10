# CalmWay Phase 3B：真实 Mapbox 步行路线

## 架构

Phase 3B 的数据流是：

```text
React /routes/search
    -> POST /api/v1/routes/walking
    -> FastAPI WalkingRoutingService
    -> MapboxDirectionsClient
    -> Mapbox Directions API
    -> CalmWay 标准化路线 DTO
    -> React /routes/options
```

Directions 由后端负责，因为后续路线采样、Crowd Exposure 计算、响应验证和外部 API 配置都属于后端边界。`MAPBOX_ACCESS_TOKEN` 只在 FastAPI 进程内使用，不会返回到浏览器。

## CalmWay 请求

前端只提交 Phase 3A 已确认的坐标和已保存的 crowd tolerance：

```json
{
  "origin": {
    "label": "Flinders Street Station",
    "longitude": 144.9671,
    "latitude": -37.8183
  },
  "destination": {
    "label": "Melbourne Central",
    "longitude": 144.9631,
    "latitude": -37.8102
  },
  "preference": "PREFER_QUIETER"
}
```

后端验证经度为 `-180..180`、纬度为 `-90..90`，并拒绝 NaN、Infinity 和无效类型。本阶段不把文字重新 geocode。

## Mapbox Directions 请求

后端调用：

```text
GET https://api.mapbox.com/directions/v5/mapbox/walking/
    {originLongitude},{originLatitude};
    {destinationLongitude},{destinationLatitude}
```

坐标顺序始终是 longitude、latitude，Origin 在前，Destination 在后。请求参数是：

- `alternatives=true`
- `geometries=geojson`
- `overview=full`
- `steps=true`
- `language=en`
- `access_token`（仅后端环境变量）

`alternatives=true` 只是请求 Mapbox 尝试返回替代路线，不保证一定有多条路线。CalmWay 接受一条路线；若 Mapbox 返回多条有效路线，则保持原始顺序，不复制主路线，也不制造 mock alternatives。

## 标准化路线

每条路线保存：

```ts
{
  id: "mapbox-route-0";
  source: "MAPBOX";
  routeIndex: 0;
  name: "Walking route";
  distanceMeters: number;
  durationSeconds: number;
  geometry: {
    type: "LineString";
    coordinates: [longitude, latitude][];
  };
  steps: {
    instruction: string;
    distanceMeters: number;
    durationSeconds: number;
    maneuverLocation: [longitude, latitude] | null;
  }[];
}
```

主路线显示为 `Walking route`，后续路线显示为 `Alternative route 1`、`Alternative route 2`。这些只是顺序标签，不是推荐结果。

## Geometry 与 steps

后端保留 `overview=full` 返回的完整 GeoJSON LineString，不做 polyline 转换、简化、插值或 50 m 采样。每条 geometry 坐标都经过 finite / longitude / latitude 验证。

后端从 `legs[].steps[]` 只保留 Mapbox 官方步骤字段中的 `maneuver.instruction`、step distance、step duration 和 `maneuver.location`。步骤缺失或单个步骤无效时，路线 geometry、distance、duration 仍然可用。

## Crowd 与 tolerance

Phase 3B 没有真实路线级 Crowd Exposure，因此路线 DTO 不包含假的 LOW / MEDIUM / HIGH，也没有 `recommended=true`。用户 tolerance 仍保存在 JourneyContext 并显示在 Route Options，但不会排序、过滤或推荐路线。

## 测试

运行 Directions mocked tests：

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_mapbox_directions_client.py tests/test_walking_routing_service.py tests/test_routes_api.py
```

运行全部普通测试（不会访问 Mapbox 网络）：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

只有明确设置 gate 后才运行真实 Mapbox integration：

```powershell
$env:RUN_MAPBOX_DIRECTIONS_INTEGRATION="1"
.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_mapbox_directions_live_integration.py
Remove-Item Env:RUN_MAPBOX_DIRECTIONS_INTEGRATION
```

真实 token 继续来自 ignored `backend/.env` 的 `MAPBOX_ACCESS_TOKEN`，不要把 token 放入命令、测试或文档。

## 本地手动测试

启动后端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000
```

启动前端：

```powershell
cd frontend
npm.cmd run dev
```

打开 `http://localhost:5173/routes/search`，在 Starting point 选择 `Flinders Street Station`，在 Destination 选择 `Melbourne Central`，选择任意 tolerance，然后提交。Route Options 应显示 Mapbox 返回的实际路线数量、实际 distance 和 duration，不应显示 Garden Streets、Direct City Walk 或假的 crowd badge。

开发模式下 Route Options 的 `Development check` 会显示首条路线的 source、geometry type、坐标数量、distance、duration 和 step count，但不显示 token 或完整坐标数组。

## API 单独检查

后端启动后，可在 PowerShell 使用：

```powershell
$body = @{
  origin = @{ label = "Flinders Street Station"; longitude = 144.9671; latitude = -37.8183 }
  destination = @{ label = "Melbourne Central"; longitude = 144.9631; latitude = -37.8102 }
  preference = "PREFER_QUIETER"
} | ConvertTo-Json -Depth 4

Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/v1/routes/walking" -ContentType "application/json" -Body $body
```

Phase 3B 不绘制 route line、不添加 markers、不进行 route sampling 或 crowd ranking。地图路线绘制从 Phase 3C 开始。

参考：[Mapbox Directions API 官方文档](https://docs.mapbox.com/api/navigation/directions/)。
