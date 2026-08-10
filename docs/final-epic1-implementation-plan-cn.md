# CalmWay Epic 1 最终实施计划（中文版）

## 1. 文档定位

本文记录 CalmWay FIT5120 项目 Epic 1 的最终产品流程、数据算法边界、技术架构和分阶段实施计划。

当前仓库完成的是“产品交付 Phase 1：架构与界面流程”。它与数据科学交接包中的后端实施顺序并不矛盾：交接包的数据库、历史基线、实时摄取、空间计算等步骤将在本项目后续 Phase 2 及以后按原顺序实施。

数据科学与后端算法的唯一权威来源是：

```text
handoff/epic1_backend_handoff_v3/
```

任何后续实现都不得用前端三档展示、P33/P67、固定人数阈值或其他简化逻辑替换该交接包。

## 2. 最终五屏流程

```text
未来 Home
  → Route Search（路线搜索）
  → Route Options（路线选项）
  → Active Navigation（导航中）
      → 可选 Crowd Alert（导航页内的拥挤提醒状态）
  → Arrival（到达/结束导航）
  → 未来 Home
```

| 屏幕/状态 | 主要职责 | 当前 Phase 1 状态 |
| --- | --- | --- |
| Route Search | 起点、终点、当前位置、单选人群容忍度、免责声明 | 已建立；手动文本与一次性浏览器定位可用，Mapbox 地址建议待接入 |
| Route Options | 展示 1–3 条候选步行路线、距离、时间、三档人群等级、推荐状态和 Depart | 已建立；当前使用两条明确标注的模拟路线 |
| Active Navigation | 地图、完整路线、当前位置、目的地、下一步指令、剩余距离/时间、进度 | 已建立响应式预览；尚无 Mapbox 和持续 GPS |
| Crowd Alert | 当后续路段超过用户偏好时，在导航页内提醒并提供两个操作 | 已建立可测试状态；尚无真实周期重算或重路由 |
| Arrival | 目的地、完成确认、总时间、总距离、旅程人群负荷、结束导航 | 已建立；当前汇总来自所选模拟路线 |

Crowd Alert 不是独立页面路由，而是 Active Navigation 的状态。

## 3. 用户故事与屏幕对应关系

### US 1.1

用户希望查看不同步行路线的 LOW / MEDIUM / HIGH 人群或感官指标，以选择较不压迫的路线。

对应屏幕：

- Route Search：输入行程并选择一个人群容忍度；
- Route Options：比较候选路线及三档人群等级；
- Arrival：查看整段旅程的人群负荷摘要。

### US 1.2

系统识别高人流步行区域，并优先推荐能减少高人流暴露的路线。

对应屏幕与服务：

- Route Options 展示后端推荐结果；
- 推荐必须来自 CalmWay 人群暴露排序，不能简单选择最短的 Mapbox 路线；
- 后端路线评估使用 P75 Crowd Exposure 作为路线等级摘要。

### US 1.3

用户选择人群容忍度；导航期间，如果前方行人活动超过该偏好，系统提醒用户，并在有更好候选路线时提供较低刺激的替代路线。

对应屏幕与服务：

- Route Search：单选容忍度；
- Active Navigation：定期对剩余路线使用最新完整 15 分钟缓存重新评估；
- Crowd Alert：`Start lower-stimulation route` 或 `Continue current route`；
- 选择替代路线后，从当前位置到同一目的地重新获取候选路线并按 CalmWay 规则排序。

该功能不得描述成逐秒人流感知。

## 4. 人群算法的权威规则

### 4.1 主指标与本地状态严格分离

主 Crowd Exposure：

```text
当前完整 15 分钟窗口的 Network percentile
```

Local Historical Percentile 只用于独立的 Local Condition：

```text
Location_ID × HourDay × Day_Type
```

禁止：

```text
MAX(Local percentile, Network percentile)
```

Local Condition 较高时，不得暗中提高主 Crowd Level。

### 4.2 后端五档等级

| Network Crowd Exposure 分数 | 后端 Crowd Level |
| ---: | --- |
| `<= 25` | `VERY_LOW` |
| `> 25 且 <= 50` | `LOW` |
| `> 50 且 <= 75` | `MODERATE` |
| `> 75 且 <= 90` | `HIGH` |
| `> 90` | `VERY_HIGH` |

这些是相对行人活动的统计分档，不是临床或医学阈值。

### 4.3 空间支持与加权

只有具有有效分数的 Outdoor 传感器可支持室外步行路线：

| 最近有效传感器距离 | 覆盖状态 |
| ---: | --- |
| `<= 250 m` | `SUPPORTED` |
| `> 250 m 且 <= 300 m` | `LIMITED` |
| `> 300 m`，或 300 m 内无有效分数 | `NO_DATA` |

空间权重必须为归一化反距离权重：

```text
w_i = 1 / max(distance_i, 1 m)

PointScore = SUM(w_i × Score_i) / SUM(w_i)
```

不得扩大半径直到找到传感器，不得累加空间上不同传感器的原始人数，也不得把 `NO_DATA` 转成 LOW。

### 4.4 完整 15 分钟窗口与数据状态

```text
完整窗口内至少 1 条有效、无冲突记录
→ OK
→ 汇总有效记录
→ 参与同窗口 Network 排名

完整窗口内 0 条有效记录
→ AMBIGUOUS_NO_RECORD
→ 当前人数与 Network percentile 为 NULL
→ 不参与排名
```

`AMBIGUOUS_NO_RECORD` 不能当作零。MVP 不使用“某传感器连续 N 分钟无记录即 STALE”的规则；`STALE` 只表示数据源或当前缓存违反运维新鲜度要求。

### 4.5 路线采样、摘要和排序

初始采样间隔：

```text
50 m（可配置，真实路线出现后进行 V7 稳定性验证）
```

路线等级摘要：

```text
P75 Crowd Exposure
```

路线排序顺序必须保持：

1. `no_data_pct ASC`
2. `pct_above_preference ASC`
3. `p75_crowd_exposure_score ASC`
4. `maximum_crowd_exposure_score ASC`
5. `duration_seconds ASC`

## 5. 后端五档到前端三档的映射

映射只发生在展示层，不改变后端算法或数据库值：

| 后端等级 | 前端展示 |
| --- | --- |
| `VERY_LOW`、`LOW` | `LOW` |
| `MODERATE` | `MEDIUM` |
| `HIGH`、`VERY_HIGH` | `HIGH` |

未知覆盖应使用独立覆盖/数据状态表达，不能伪装成前端 LOW。

## 6. 单选人群偏好映射

| 前端选择 | 后端 preference | 最大偏好 Network 分数 | 说明 |
| --- | --- | ---: | --- |
| LOW | `AVOID_BUSY` | 50 | 偏好较安静路线，适合希望避开较繁忙行人区域的用户 |
| MEDIUM | `PREFER_QUIETER` | 75 | 平衡选项，允许中等行人活动，同时仍偏好较安静路线 |
| HIGH | `FLEXIBLE` | 90 | 更灵活，需要时允许经过较繁忙区域 |

三个值通过环境变量/集中配置保留可配置性。它们是产品偏好，不得宣传成个人医学耐受度。

前端必须显示免责声明：

> Crowd levels are relative estimates based on City of Melbourne pedestrian activity data. They are not medical or safety thresholds.

## 7. Mapbox 架构

最终选用 Mapbox：

- 地图：Mapbox GL JS；
- 地址/地理编码：Mapbox Geocoding API v6 或 Mapbox Search JS Geocoder；
- 不使用 Mapbox Search Box API；
- 路线：Mapbox Directions API；
- 步行 profile：`mapbox/walking`。

Directions 请求必须支持：

```text
alternatives=true
steps=true
geometries=geojson
overview=full
language=en
```

Mapbox 只提供可步行路线几何、距离、时间和 maneuver。CalmWay 后端负责传感器人群证据、路线评估与推荐排序。Mapbox 返回少于三条路线时，前端必须正常展示实际返回数量。

安全边界：

- 前端只使用 `VITE_MAPBOX_PUBLIC_TOKEN`；
- 后端只使用 `MAPBOX_ACCESS_TOKEN`；
- 真实令牌不得硬编码或提交；
- 服务器秘密凭证不得暴露给 React。

Phase 1 仅建立 `services/mapbox.ts` 配置边界，没有调用 Mapbox，也没有提前加入 Mapbox GL 依赖。

## 8. PostgreSQL/PostGIS 架构

最终数据库固定为 PostgreSQL + PostGIS，起始 schema 为：

```text
handoff/epic1_backend_handoff_v3/05_DATABASE_SCHEMA.sql
```

主要职责包括：

- 传感器当前位置与 Outdoor 类型；
- 历史小时记录及 `(Location_ID, Sensing_Date, HourDay)` 自然键；
- 原始分钟记录、payload hash、重复和冲突保留；
- Local 与 Network 历史基线；
- 当前传感器活动缓存；
- PostGIS 空间查询与空间结果缓存。

Phase 1 不创建数据库、不执行 schema，也不使用 SQLite。当前 `db/` 与 `repositories/` 只提供后续实现边界。

## 9. Phase 1 已完成的变更

### 前端

- 建立 React Router 四个页面路由和五屏/状态流程；
- 建立轻量 `JourneyContext`，不使用 Redux；
- 建立单选 crowd preference、三档展示类型和五档到三档纯展示映射；
- 建立路线卡片、导航地图占位区、maneuver、剩余时间/距离、进度、提醒与到达状态；
- 建立 Mapbox 和后端 API 服务边界；
- 保留一次性浏览器当前位置输入，但没有持续 GPS 跟踪；
- 所有模拟结果和状态预览均明确标注为 Phase 1。

### 后端

- 建立 `api/`、`models/`、`schemas/`、`services/crowd/`、`services/routing/`、`services/navigation/`、`repositories/`、`db/` 边界；
- 建立内部五档、前端三档、偏好、覆盖和数据状态枚举；
- 建立环境配置模型，并保存 250/300 m、1/d、50 m、P75 和排序顺序；
- 保留原模拟接口和服务兼容层，使现有应用与测试继续运行；
- 没有实现任何真实人群计算。

### 配置与文档

- 准备前后端 Mapbox、Home、数据库、人群偏好和算法环境变量；
- 更新 README、架构、验收范围、团队和数据目录说明；
- 新增本文档；
- `.env` 继续被 Git 忽略，`.env.example` 可安全提交。

## 10. 后续 Phase 2–5

### Phase 2：数据库、历史数据与当前分数

- 按权威 schema 建立 PostgreSQL/PostGIS；
- 摄取传感器、小时历史和分钟实时记录；
- 实现重复、冲突、时区、完整窗口和数据状态；
- 构建 Local/Network 基线，并执行 Location 14、37、47、181 的迁移规则；
- 实现当前 15 分钟 Network percentile 和独立 Local Condition。

### Phase 3：空间引擎与 Mapbox 路线

- 实现 250/300 m PostGIS 查询和归一化 1/d；
- 接入 Mapbox Geocoding v6、GL JS 和 Directions；
- 按 50 m 采样真实路线；
- 计算覆盖率、P75、最大值、超偏好比例并按冻结顺序排序；
- 支持 Mapbox 实际返回的 1–3 条候选路线。

### Phase 4：真实导航和提醒

- 持续 GPS、路线进度和 maneuver 更新；
- 使用最新完整 15 分钟缓存周期性评估剩余路线；
- 实现真实 Crowd Alert、从当前位置重算路线及替代路线切换；
- 完成真实到达检测和旅程汇总。

### Phase 5：验证、部署与运维

- 使用真实路线执行 V7 的 25/50/75/100 m 采样稳定性比较；
- 增加摄取、基线、PostGIS、路线、导航和错误状态测试；
- 配置缓存新鲜度、数据源和 Mapbox 错误监控；
- 完成部署、安全配置和端到端验收。

## 11. 已知范围排除和冲突说明

### 冲突 1：公共交通

旧版 DoD 提到公共交通接入，但最终数据科学交接明确为 walking-only，并排除公共交通路线与公共交通拥挤。本 Epic 1 不实现公共交通。

### 冲突 2：施工、活动、噪声和视觉刺激

旧原型文案提到 construction、events、noise 或 visual stimulation，但交接算法没有测量这些维度。界面和推荐不得声称已经支持这些因素。

### 冲突 3：“实时行人密度”

最终数据模型测量的是基于完整 15 分钟窗口的相对行人活动和 Network percentile，不是 persons/m² 物理密度，也不是逐秒实时传感。因此产品文案应使用 “current pedestrian activity” 或 “near-real-time pedestrian conditions”。

其他明确排除：

- 临床/医学耐受度或安全认证；
- 将 `NO_DATA` 解释为安静；
- 用 Local Condition 替代或升级主 Crowd Level；
- 当前 Phase 1 的数据摄取、真实评分、真实路线、持续 GPS、部署。

## 12. Home 集成边界

Home 页面由其他团队成员负责，本次不实现。

当前约定：

- `/` 暂时重定向至 `/routes/search`，使独立 Epic 1 应用可运行；
- 页面返回 Home 和 Arrival 的 `End navigation` 使用 `VITE_HOME_ROUTE`；
- 合并真实 Home 后，只需配置该变量并由主路由接管 Home 路径；
- Epic 1 不复制 Home 的布局、状态或业务逻辑。

## 13. Phase 1 验收原则

Phase 1 完成时必须满足：

- 原有 pytest 测试仍通过，并增加架构契约测试；
- TypeScript 与 Vite production build 通过；
- 没有 Mapbox、City 数据、PostGIS 或 GPS 的虚假成功声明；
- 模拟路线、预览控制和兼容层均可识别；
- 仓库未提交、未推送、未切换分支；
- Phase 2 可直接沿权威 handoff 继续，而不需要重做 Phase 1 页面和模块边界。
