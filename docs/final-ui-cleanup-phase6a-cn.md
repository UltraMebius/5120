# CalmWay Phase 6A：最终产品界面清理

## 目标与范围

Phase 6A 只清理普通用户能够看到的文字、诊断面板和开发标签，使 Epic 1
流程可以作为正常产品使用。后端数据契约、路线算法、人流算法、Mapbox 请求、
数据库和部署均未改变。

## 已移除的开发界面

- 删除 Search 页的 Epic/Phase 徽章；
- 删除地点选择后的经纬度 Development check；
- 删除 Route Options 中的 source、geometry、coordinates、duration、steps
  诊断面板；
- 删除 Search 地图上的 smoke-test/interactive 自定义标签；
- 删除路线地图上的 “Previewing” 自定义浮层；
- 把界面中的 preview、placeholder、backend、provisional MVP、LineString、
  token 等实现词汇移出普通用户流程。

代码中的 `MAPBOX`、`PROVISIONAL`、`INSUFFICIENT_DATA`、GeoJSON 类型和 Phase
历史注释仍可保留，因为它们是内部契约或开发文档，不会直接显示给用户。

## Search 最终文字

页面继续使用 CalmWay 和 “Find a calmer way there”。说明现在只引导用户选择
起点、终点和人流容忍度。地点帮助文字为：使用当前位置，或选择起点和终点。
加载状态改为 “Finding walking routes...”。地点验证只要求用户从建议中选择，
不再解释 Mapbox session、坐标或 API 流程。

LOW、MEDIUM、HIGH 的含义和阈值完全不变。主界面继续使用容易理解的描述，
不显示 50/75/90 内部阈值。

## Route Options 最终文字

页面保留 “Choose your walk”、起终点、容忍度、路线卡、地图、距离、预计时间、
推荐状态和 Depart。路线来源标签改为 “Walking route”；地图动作改为
“View on map / Shown on map”。

有数据时，页面说明路线结合当前行人活动和用户容忍度排序，但不显示 backend、
MVP、P75 或 provisional 等词。路线卡只显示人流等级和偏好结果，不显示内部
`/100` 分数。数据不足时统一显示：人流信息当前不可用，但步行路线仍可查看和
使用。

## Navigation 最终文字

Navigation 继续显示目的地、返回按钮、步行标识、地图、第一条现有路线指令、
距离和预计时间。静态限制改为自然语言：

> Route overview. Live location and progress tracking are not enabled.

Navigation 底部状态面板提供普通的次要操作 “End route overview”。它只把
当前 JourneyContext 中已经选择的路线带到 `/arrival` 路线摘要，不清空状态、
不推断用户已经到达，也不会发出新的后端或 Mapbox 请求。

`CLEAR` 仅显示低干扰说明，不宣称前方安全、安静或无人。`ALERT` 继续显示
“Busier pedestrian activity ahead”、偏好说明、Continue current route，以及
仅在严格资格规则满足时出现的 Start lower-stimulation route。警报说明现在
表示数据来自路线搜索时可用的前方数据，且不会实时更新。

数据不足时只用一个主要状态卡显示 “Crowd information unavailable”，并说明
前方当前数据不足以评估所选偏好；不会显示 LOW、CLEAR 或推荐。

## Arrival 最终文字

Arrival 的主标题为 “Route summary”，并保留 End navigation。它只显示现有
计划路线的 Planned distance、Estimated time 和 Selected tolerance。页面明确
说明没有跟踪实时路线进度或实际步行时间，因此不会声称用户已经到达，也不会
伪造完成时间、实际步行距离或实际人流暴露。

默认 Home 集成页面不再显示 placeholder 或团队分工文字，只显示导航已结束，
并提供重新规划路线的入口。`VITE_HOME_ROUTE` 集成边界保持不变。

## 为什么隐藏技术术语

`P75`、numeric samples、GeoJSON、LineString、routeIndex、rankingStatus、
PostGIS 和 API 提供方属于实现契约，不帮助普通用户作出路线选择。它们仍保留
在代码和开发文档中，但最终界面将其翻译成路线、人流信息、推荐和不可用状态。

## 为什么保留免责声明与静态限制

人流等级是相对行人活动估计，不是人数密度、医疗建议或安全保证，所以 Search
和 Route Options 继续显示简洁免责声明。Navigation 也必须说明没有实时位置和
进度跟踪，避免让用户误以为这是实时 turn-by-turn 导航。

## 桌面与移动检查

桌面检查目标为约 1440×900：Search 居中、Route Options 卡片与地图平衡、
Navigation 浮层不冲突、Arrival 摘要清晰。移动检查目标为 390×844：无横向
溢出、输入和容忍度卡可操作、路线地图可见、Navigation 状态与按钮可读可点、
Arrival 可用。Mapbox/OpenStreetMap 法定 attribution 由 Mapbox GL JS 保留，
本阶段没有隐藏或覆盖。

## Phase 6B 与未改变内容

Phase 6B 的具体范围应由后续项目说明确认；可能的最终验收、团队 Home 集成或
其他交付工作不在本阶段提前实现。Phase 6A 明确没有改变：250/300 米空间支持
规则、反距离加权、50 米采样、55% 覆盖门槛、P75、偏好阈值、Phase 4 排名、
300 米/连续两个样本警报规则、替代路线资格、Search/Direction 请求、数据库、
City refresh、AWS、认证、实时 GPS、自动重规划或任何环境变量与密钥。
