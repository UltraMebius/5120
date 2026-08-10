# CalmWay Phase 3A：Mapbox 地点 / POI 搜索

## 本阶段范围

Phase 3A 在 `/routes/search` 的 Starting point 和 Destination 字段中接入 Mapbox Search Box API。地图继续显示 Melbourne CBD，但本阶段不添加标记，也不调用 Directions API。

## `/suggest` 与 `/retrieve`

- 用户输入至少 3 个字符后，前端等待 300 ms，再调用 `GET https://api.mapbox.com/search/searchbox/v1/suggest`。
- `/suggest` 返回名称、地址上下文及 `mapbox_id`，但不把建议结果当作最终坐标。
- 用户选择建议后，前端使用该 `mapbox_id` 调用 `GET https://api.mapbox.com/search/searchbox/v1/retrieve/{mapbox_id}`。
- `/retrieve` 返回 GeoJSON Point；前端验证响应后保存经度、纬度和完整地点资料。坐标顺序始终是 longitude、latitude。

## `session_token` 生命周期

Starting point 和 Destination 各自拥有独立的 UUIDv4 风格 session token，因此两个并发输入不会错误共享会话。同一轮输入中的所有 `/suggest` 与最终 `/retrieve` 使用同一个 token。成功 `/retrieve` 后，该字段立即准备一个新 token，供下一轮独立搜索使用；清空输入也会开始一个新会话。未完成 retrieve 的 Mapbox 会话将按 Mapbox 的服务规则过期。

## 为什么保存结构化地点

每个已确认地点保存以下临时旅程数据：

```ts
{
  mapboxId: string;
  name: string;
  fullAddress: string;
  longitude: number;
  latitude: number;
}
```

Phase 3B 的 Directions 请求需要可靠的 origin / destination 坐标。只保存输入文字无法区分同名地点，也无法安全请求路线。

## 编辑文字为什么会取消选择

如果用户选择地点后又修改输入，旧的结构化地点会立即设为未确认。这样不会把已经改变的文字与旧坐标组合，也不会将 stale coordinates 传给以后阶段。提交前，两个字段都必须重新从 Mapbox 建议中选择。

## Melbourne 相关性设置

`/suggest` 使用：

- `country=AU`
- `proximity=144.9631,-37.8136`
- `language=en`
- `limit=5`
- `types=poi,address,place,locality,neighborhood,street`

proximity 只提高 Melbourne CBD 附近结果的相关性，不使用任意 bounding box，也不会人为排除附近有效地点。

## Public token

浏览器端只通过现有 Mapbox 配置读取：

```text
VITE_MAPBOX_PUBLIC_TOKEN
```

token 应保存在被 Git 忽略的 `frontend/.env` 中，不得硬编码、打印或提交。

## 手动测试

1. 在 `frontend` 目录运行 `npm run dev`（若 PowerShell 阻止 `npm.ps1`，运行 `npm.cmd run dev`）。
2. 打开 `http://localhost:5173/routes/search`。
3. 在 Starting point 输入 `Flinders Street Station`，等待建议，使用鼠标或方向键加 Enter 选择正确的 Melbourne 结果。
4. 确认字段下方显示 Selected 地址。在开发模式中还会显示仅用于验证的 longitude / latitude；不会显示 token。
5. 在 Destination 输入 `Melbourne Central` 并选择正确结果，确认同样保存坐标。
6. 修改任一已选字段文字，确认 Selected 和开发坐标提示消失；直接提交时应提示重新选择建议。
7. 输入无意义文字，确认出现空结果或简短错误提示，页面不崩溃。
8. 两个字段均确认后提交，现阶段仍进入 Phase 1 route preview。

## 尚未实现

Phase 3A 没有实现 Mapbox Directions、walking route geometry、距离、时长、路线 alternatives、地图标记或自动 fly-to。这些属于后续阶段。

参考：[Mapbox Search Box API 官方文档](https://docs.mapbox.com/api/search/search-box/)。
