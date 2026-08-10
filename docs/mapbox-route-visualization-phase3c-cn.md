# CalmWay Phase 3C：真实 Mapbox 路线可视化

## 范围

Phase 3C 在 Route Options 和 Navigation 页面绘制 Phase 3B 已返回的真实步行路线。它只修改前端展示层，不新增后端接口，也不会再次请求 Mapbox Directions。

本阶段明确不实现路线采样、Crowd Exposure、路线排名、实时 GPS、导航进度或动态重规划。

## 数据流

```text
POST /api/v1/routes/walking
    -> WalkingRoute.geometry（GeoJSON LineString）
    -> JourneyContext.routes
    -> Route Options 的预览路线
    -> Depart 保存 JourneyContext.selectedRoute
    -> Navigation 复用同一个 selectedRoute
```

Route Options 默认预览后端返回的第一条路线。选择其他路线卡片的“Preview on map”后，地图更新为该路线；点击“Depart”保存被点击的同一条路线并进入 Navigation。Navigation 不重新调用 Directions。

## RouteMap 组件

`frontend/src/components/map/RouteMap.tsx` 是两个页面共用的路线地图组件，继续使用项目已有的 Mapbox GL JS 配置和 `mapbox://styles/mapbox/standard` 样式。

组件负责：

- 把 `WalkingRoute.geometry` 作为 GeoJSON source；
- 用一个中性的 CalmWay 绿色 line layer 绘制整条路线；
- 显示不同样式的起点 A 和终点 B marker；
- 使用全部 geometry 坐标以及起终点计算 bounds；
- 调用 `fitBounds`，使用响应式 padding 和 `maxZoom: 16`；
- 路线切换时更新现有 GeoJSON source 和 marker；
- Mapbox style 重新加载后重新添加 source/layer；
- React effect 清理时移除 marker、事件监听和 map 实例。

地图只在路线或 style 真正变化时重新 fit，不使用任意 `setTimeout`。起点 marker 表示路线起点，不代表实时用户位置。

## Geometry 验证与失败状态

渲染前必须满足：

- geometry 类型为 `LineString`；
- 至少包含两个坐标；
- 每个坐标都是 `[longitude, latitude]`；
- 经度、纬度都是有限数值，并位于合法范围；
- 起点和终点坐标也有效。

如果 token 缺失、geometry 无效、地图初始化失败或路线绘制失败，页面会在地图区域显示受控提示。路线卡片和其他页面操作仍然可用，不会显示空白画布，也不会退回假的示意路线。

## Navigation 的静态边界

Navigation 显示真实 basemap、真实完整路线、真实起终点、实际距离/时长，以及 `route.steps[0]` 的第一条指令。若步骤缺失，会显示安全的 fallback 指令。

页面明确标注它是静态路线概览：本阶段不显示假的当前位置，也不显示假的进度百分比。

## 本地验证

启动后端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000
```

启动前端：

```powershell
cd frontend
npm.cmd run dev
```

打开 `http://localhost:5173/routes/search`：

1. 从 Mapbox suggestions 选择 `Flinders Street Station` 作为起点。
2. 从 Mapbox suggestions 选择 `Melbourne Central` 作为终点。
3. 提交后确认 Route Options 显示真实 basemap、完整路线、A/B marker，并且视野包含整条路线。
4. 如果返回多条路线，逐条点击“Preview on map”，确认 line 和 bounds 对应更新。
5. 对当前预览路线点击“Depart”，确认 Navigation 显示同一条路线，并显示真实第一条 maneuver。
6. 在桌面与窄屏尺寸检查地图、卡片、marker、Mapbox controls 和底部状态卡没有关键遮挡。
7. 检查浏览器 console，确认没有 source/layer 重复、style-load 时序或 React Strict Mode 清理错误。

生产构建：

```powershell
cd frontend
npm.cmd run build
```

参考：[Mapbox GL JS 添加 GeoJSON line](https://docs.mapbox.com/mapbox-gl-js/example/geojson-line/)、[按 LineString 调整地图范围](https://docs.mapbox.com/mapbox-gl-js/example/zoomto-linestring/)。
