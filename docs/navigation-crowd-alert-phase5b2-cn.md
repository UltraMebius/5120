# CalmWay Phase 5B-2：导航人流提示与既有替代路线切换

## 端到端流程

用户在 Route Search 选择起点、终点和人流偏好后，只调用一次
`POST /api/v1/routes/walking`。后端依次得到 Mapbox 步行候选路线、Phase 3E
逐点结果、Phase 4 聚合与排名，并使用同一个 `RouteCrowdEvaluation` 计算
Phase 5B-1 初始提示。用户在 Route Options 点击 Depart 后，Navigation 直接
使用这次响应里的路线和 `initialCrowdAlert`，不会再次请求 Directions。

## 为什么初始进度固定为 0

Phase 5B-2 仍然是静态路线预览，所以调用参数严格为
`current_progress_meters=0`。它仅表示“从路线起点评估前方 300 米”，不表示
浏览器通过 GPS 测得用户正在起点。当前没有 `watchPosition`、持续定位、路线
吸附、转弯推进、偏航、自动重规划或到达检测。

## 三种状态

- `ALERT`：Navigation 显示“Busier pedestrian activity ahead”卡片，说明在
  返回的前视距离内发现持续高于用户偏好的行人活动。区间文字只使用后端
  返回的 trigger 距离，不生成街道名，也不声称危险、不安全或医疗风险。
- `CLEAR`：不显示警报卡，只用低干扰文字说明“当前可用的路线前方数据没有
  触发提示”。它不保证安静、无人或安全。
- `INSUFFICIENT_DATA`：显示“Crowd monitoring unavailable”和数据不足说明。
  Mapbox 路线、距离、时间和第一条步行指令仍可使用；不能把数据不足显示成
  LOW、CLEAR 或推荐。

真实 current materialisation 可能是 0 个数值样本、0% 覆盖。这个真实状态
应正常进入 `INSUFFICIENT_DATA`，不能为了演示而伪造 ALERT。受控 API fixture
和浏览器 fetch mock 可验证三种界面，不会修改真实数据库或生产逻辑。

## Continue current route

点击 “Continue current route” 只在当前前端 Navigation 会话里记录该路线已
确认，并隐藏该路线的警报卡。它不修改后端 `ALERT` 决策、不声称人流已经
消失、不改变路线，也不写数据库或 localStorage。确认记录按 route ID 区分。

## 更低刺激替代路线的资格

只有当前路线 P75 是数值，并且同一次后端响应中按现有顺序扫描到的第一条
候选路线同时满足以下全部条件，才显示 “Start lower-stimulation route”：

1. 不是当前路线；
2. 已存在于 `JourneyContext.routes`；
3. Phase 4 `rank` 非空且 P75 是数值；
4. `preferenceStatus` 不是 `INSUFFICIENT_DATA`；
5. `initialCrowdAlert.decision` 是 `CLEAR`；
6. 候选 P75 严格低于当前路线 P75。

前端只做线性扫描，不排序、不重新定义 Phase 4 排名。只有一条路线、当前
P75 为空、候选数据不足或 P75 没有严格更低时，都不显示按钮。系统绝不会
伪造替代路线。

点击后，`selectedRoute` 切换为这条已经存在的候选路线，RouteMap 几何、距离、
时间和第一条 normalized Mapbox step 随状态更新。该动作没有新网络请求，
因此应称为“既有替代路线切换”，不是实时或自动 rerouting。

## 未来扩展点

未来实时导航阶段可以把经过定义和验证的实测路线进度传给现有纯 Phase 5B-1
服务，再决定更新频率、定位权限、偏航和旧提示处理规则。本阶段不提前实现或
假装具备这些能力。
