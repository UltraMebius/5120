# CalmWay Phase 5A：一次性当前位置起点

Phase 5A 把搜索页的“Use my location”接入浏览器 Geolocation API，并把结果作为现有步行路线流程的真实起点。范围到一次性起点获取为止；没有实现持续定位或 Crowd Alert。

## 一次性流程

定位只会由用户点击按钮触发，页面加载时不会自动请求权限：

```text
Use my location
  -> navigator.geolocation.getCurrentPosition(...)
  -> 浏览器权限与一次位置结果
  -> JourneyContext 内存中的 GEOLOCATION 起点
  -> Destination 继续由 Mapbox Search Box 选择
  -> POST /api/v1/routes/walking
  -> 现有 Phase 4 路线评估与排名
```

采用的浏览器选项是：

- `enableHighAccuracy: true`
- `timeout: 10000` 毫秒
- `maximumAge: 30000` 毫秒

定位进行时按钮显示 `Locating...` 并禁用，防止重复请求。Destination 输入仍可操作。成功后起点显示 `Current location`；开发模式可显示简短经纬度检查，生产构建不显示这些坐标。

## 来源数据模型

结构化位置使用判别字段区分来源：

- `MAPBOX`：保留原有 `mapboxId`、`fullAddress`、名称和坐标；
- `GEOLOCATION`：只包含 `source: "GEOLOCATION"`、`label/name: "Current location"`、真实 `longitude` 和 `latitude`。

浏览器位置不是 Mapbox 搜索结果，因此不会制造假的 `mapboxId` 或 `fullAddress`。路线接口只需要标签和坐标，所以不需要为 GPS 坐标额外调用 Mapbox reverse geocoding。前端向现有后端路线请求仍只发送 `label`、`longitude`、`latitude` 和人群偏好，不发送来源、浏览器元数据或 Mapbox ID。

浏览器返回 `latitude` 与 `longitude` 后分别按同名字段保存；进入需要坐标数组的路线/地图边界时仍保持 `[longitude, latitude]` 顺序。

## 编辑、清除与失败

定位成功会在成功结果到达后替换旧起点，但不会修改 Destination。用户编辑或清除 `Current location` 时，GEOLOCATION 结构会立即从表单及 JourneyContext 清除，输入框恢复普通 Mapbox 建议流程，不会继续使用旧 GPS 坐标。之后也可选择任意 Mapbox 起点。

如果新定位失败，之前有效的起点会保留。界面分别处理：

- 权限拒绝：提示允许权限或手动输入；
- 位置不可用：提示无法确定位置并允许手动输入；
- 超时：提示重试或手动输入；
- 浏览器不支持：提示当前浏览器无法定位。

错误与 Starting point 控件关联，不显示浏览器堆栈，也不会绕过浏览器权限。

## 隐私与部署

精确位置只保存在当前页面的 JourneyContext/session memory，并仅在用户提交路线时作为现有路线请求的起点发送。实现没有写 PostgreSQL、`localStorage` 或其他持久化，也不会在生产 console 输出坐标。

Geolocation 面向 secure context。localhost 可用于本地开发；生产部署必须使用 HTTPS，否则浏览器可能不提供位置能力。Phase 5A 不包含部署工作。

## 浏览器验证

### Clayton 真实位置

1. 在 Clayton 的设备上用 localhost 或 HTTPS 打开 `/routes/search`。
2. 点击 `Use my location` 并允许权限。
3. 确认 Starting point 显示 `Current location`。
4. 从 Mapbox 建议选择 Destination 并提交。
5. Clayton 可能在 City sensor coverage 之外；`NO_DATA` / `INSUFFICIENT_DATA` 是正确结果，不应伪造人群值。

### Chrome / Edge 模拟 Melbourne CBD

1. 在 DevTools 的 Sensors 中覆盖位置：latitude `-37.818272`、longitude `144.967056`。
2. 点击 `Use my location`。
3. 选择 `Melbourne Central` 为 Destination 并提交。
4. 确认路线请求使用模拟起点，正常进入真实 Mapbox Directions 与既有 Phase 4 pipeline。

### 权限拒绝与恢复

1. 把站点 Location 权限设为 Block 后点击按钮。
2. 确认出现权限拒绝提示，页面没有崩溃。
3. 在 Starting point 输入并选择 Mapbox 建议，确认手动搜索仍可使用。
4. 也应分别用浏览器模拟位置不可用和超时，确认受控提示及旧有效起点保留。

窄屏可在约 `390 x 844` 检查按钮、输入框、清除操作和错误文案没有水平溢出。

## 明确未实现

本阶段没有 `watchPosition`、持续 GPS、heading、路线吸附、实时进度、偏航检测、重规划、后台定位或到达检测。Navigation 仍是静态预览。Phase 5B 仍然是 Crowd Alert；Phase 5A 没有提前实现任何 alert 行为。
