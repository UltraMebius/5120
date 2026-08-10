# CalmWay Home 页面集成说明

## 集成范围

本次工作只把 Jiayi 负责的 Home 页面接入当前 `hongrui` 分支，不属于 Phase
6B。参考来源是 `origin/jiayi` 的提交 `4779bf0`。该提交中的旧版 `App.tsx`
使用组件内 `useState` 在 Home 与 Search 之间切换，与当前项目的 React Router
和 `JourneyContext` 架构不兼容，因此没有复制。原型的视觉方向（清晰的品牌、
主标题、功能卡片和主要行动按钮）被重新实现为独立的 `HomePage`。

## 路由与状态

- `/` 使用 React Router 重定向到 `APP_CONFIG.homeRoute`；默认值是 `/home`。
- 配置后的 Home 路径直接渲染 `HomePage`。
- Home 的主要行动按钮使用 React Router `Link` 前往 `/routes/search`，不会刷新
  整个页面。
- Search、Route Options、Navigation、Route summary 继续使用同一个
  `JourneyProvider`，现有路线状态结构没有改变。
- Route summary 的 `End navigation` 会先调用现有的 `resetJourney()`，再返回
  配置后的 Home 路径。下一次从 Home 开始规划时，上一段旅程的起点、终点、
  偏好、候选路线和选中路线不会保留。

## Home 页面内容

主要行动按钮文字为 `Find a Sensory-Friendly Route`。三个功能卡片只描述项目中
已经实现的功能：

1. `Calmer route choices`：使用行人活动估计比较步行路线；
2. `Crowd-aware preferences`：为旅程选择人群容忍度；
3. `Route-ahead crowd alerts`：在可用行人数据表示前方较繁忙时显示提醒。

页面没有宣称噪音、施工、活动、安静地点、实时导航、实时人群检测或实测到达。
路线插图是装饰性内联 SVG，不会调用 Mapbox。Home 没有加入无功能的菜单按钮。

## 保留的产品边界

- Home 不发出后端、数据库、Mapbox Search 或 Mapbox Directions 请求；
- Home 不修改路线选择、排序、采样、人群评估或提醒算法；
- Navigation 仍是静态路线概览，不推断实时位置、进度或到达；
- Route summary 只显示已有的计划信息，并保留未追踪实际旅程数据的说明；
- `VITE_HOME_ROUTE` 必须是当前前端 Router 内部路径。

## 验证清单

桌面使用 `1440 x 900`，移动端使用 `390 x 844`，检查：

1. Home 的内容居中，桌面 Hero 左右分栏，移动端按单列顺序排列；
2. 页面与主要行动按钮没有水平溢出，卡片文字完整可读；
3. Home 主要按钮进入 Route Search，并保持同一浏览器文档；
4. 完整流程为 Home → Route Search → Route Options → Navigation → End route
   overview → Route summary → End navigation → Home；
5. 返回 Home 后再次开始规划，Search 输入为空，不出现上一段旅程的数据；
6. Home 转场以及 Navigation → Route summary 不产生额外 walking API 或
   Mapbox Directions 请求；
7. 浏览器控制台没有新增错误，并通过 `npm.cmd run build`。

本次集成没有修改 backend 文件，因此不需要重复运行完整 backend pytest。

## 本次验证结果

- `1440 x 900`：Home 内容宽度居中，Hero 左右分栏，完整 Home → Home 流程通过；
- `390 x 844`：Hero、插图和三张卡片单列排列，CTA 可用且没有水平溢出，
  Home → Search 通过；
- 第一段旅程只有一次 `POST /api/v1/routes/walking`，进入 Route summary 和
  返回 Home 都没有额外请求；前端 Mapbox Directions 请求为 0；
- 返回 Home 后第二次进入 Search，起点和终点为空，第二次规划成功；
- 浏览器检查没有控制台错误或页面异常；`npm.cmd run build` 通过，只有既有的
  Mapbox bundle 大小警告。
