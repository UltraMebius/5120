# CalmWay 最终验收指南

本指南供团队在本地复验，并作为未来 AWS/public URL 验收的基础。不得用修改真实
数据库、真实 `.env` 或伪造产品数据的方式制造测试状态。

## 1. 验收前服务

- Frontend：React/Vite，默认 `http://localhost:5173`；
- Backend：FastAPI，默认 `http://localhost:8000`，`GET /health` 返回 OK；
- PostgreSQL/PostGIS：schema 与当前 crowd 数据可读；
- Mapbox：frontend public token 用于地图/Search Box，backend token 只用于
  Directions；不得在浏览器或报告中打印 token；
- 使用 Node.js 20+ 与兼容的 Python 3.12 环境。

## 2. 正常用户流程

1. 打开 `/home`，选择 `Find a Sensory-Friendly Route`；
2. 在 Search Box suggestions 中分别选择结构化 origin 和 destination；
3. 选择 LOW/MEDIUM/HIGH tolerance，提交；
4. 在 Route Options 检查路线、距离、时间、地图和 crowd 状态，使用 View on map；
5. Depart 后检查 Navigation 地图、首条 maneuver 与 crowd 状态；
6. `End route overview` → `Route summary`；
7. 确认 summary 只显示 planned distance、estimated time、selected tolerance；
8. `End navigation` → `/home`；
9. 再次进入 Search，确认上一段 journey 已清除并可规划第二段路线。

## 3. Geolocation

- 成功：显示 `Current location selected.`，只保留本次内存 journey；
- 权限拒绝、位置不可用、timeout、不支持：显示简洁的对应提示，可继续手动输入；
- pending：显示 `Locating...`，重复点击不创建第二个请求，路线提交暂时禁用，
  destination 仍可编辑；
- 定位失败不得清除之前有效的手动 origin；不得持久化精确 GPS 坐标。

部署后必须通过 HTTPS 再测试真实浏览器权限。

## 4. Crowd insufficient-data 状态

使用受控 fixture 或真实不足覆盖结果，不修改生产数据库：

- Options 仍显示 route、distance、estimated time 和 map；
- 显示 `Crowd information unavailable`；
- 不显示 fake LOW/MEDIUM/HIGH、fake recommendation；
- Navigation 仍显示路线与首条 maneuver；
- 不显示 ALERT、fake CLEAR 或 fake alternative。

ALERT、CLEAR、INSUFFICIENT_DATA 以及有/无 eligible alternative 应使用已有 pytest
与受控浏览器响应复验。Alternative switch 必须复用同一次 Search 已返回的路线。

## 5. Backend/API failure

1. 在受控环境使第一次 walking request network-fail 或返回 5xx；
2. 确认仍在 Search，显示
   `Walking routes could not be loaded. Please try again.`；
3. 确认 origin/destination 可编辑、没有 fake route、没有内部 URL/stack/token；
4. 恢复 backend 后重试，必须成功进入 Route Options；
5. 用 pytest 覆盖 upstream error、timeout、zero routes、malformed route、缺少
   backend Mapbox 配置与 database/crowd exception。

Database/crowd exception 必须保持 server error，不能转成 LOW、CLEAR、NO_DATA 或
0。不要故意损坏 PostgreSQL。

## 6. Direct URL、refresh 与 history

`JourneyContext` 只在内存中，不用 localStorage。当前确定性 guard policy 为：

| URL 缺少 journey state 时 | 当前恢复行为 |
|---|---|
| `/home` | 正常 Home |
| `/routes/search` | 正常 Search |
| `/routes/options` | 保持 URL，显示 `No route search yet` 与 `Start route search` |
| `/navigation` | 保持 URL，显示 `No active journey` 与 `View route options` |
| `/arrival` | 保持 URL，显示 `No route selected` 与 `Find a route` |
| 未知 URL | React Router replace 到 `/routes/search` |

对五个已知 URL 分别 direct-open 和 refresh；不得出现 blank page、TypeError、坏 map
或 undefined access。还要检查：

- Home → Search → browser Back/Forward；
- Options → Edit search，内存地点仍合理保留；
- Options → Navigation → Back；
- Summary → Back；
- End navigation reset 后 Back 只能看到受控空状态，不得复活旧 journey。

## 7. Desktop 与 mobile

在 `1440 x 900` 和 `390 x 844` 逐页检查 Home、Search、Options、Navigation、
Route summary：

- 无 horizontal overflow；
- 主按钮未裁切且可达；
- map 区域、状态/alert 卡片和 Home feature cards 可读；
- mobile suggestions 在 viewport 内可用；
- ALERT actions 在 mobile 不互相遮挡。

## 8. Network 与 Console

正常 planning 的 network 规则：

- Search submit：正好一次 `POST /api/v1/routes/walking`；
- Depart、Navigation、alternative switch、End route overview、End navigation、
  Home CTA：不再发 walking POST；
- frontend 不直接请求 Mapbox Directions；basemap style/tile 请求正常；
- loading 中快速重复 submit 仍只有一个 walking POST。

正常完整流程的 Console 必须没有未捕获 exception、TypeError、Unhandled Promise
Rejection 或 React render error。受控失败可以有单条内部 sanitized log，但用户页面
不得显示技术细节，不得重复失败请求。

## 9. Keyboard 与基本 accessibility

- 用 Tab/Shift+Tab 检查 Home CTA、Search fields、tolerance radio、submit、route
  buttons、Navigation actions 和 End navigation；
- suggestions 使用 Arrow Up/Down/Enter；
- tolerance radios 使用标准键盘行为；
- 检查 label、legend、button/link accessible name；
- ALERT 与 unavailable 状态必须有文字/role，不能只靠颜色；
- 不得有 keyboard trap 或无功能 hamburger。

## 10. Build、tests 与数据完整性

```powershell
cd frontend
npm.cmd run build
cd ..
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe .\scripts\check_database.py
```

必须 0 failed；既有 Mapbox bundle-size warning 可接受。若执行 database-involving
tests，使用 read-only 或 rollback fixture，并比较预期行数：

```text
pedestrian_hourly_count = 1,182,041
sensor_hour_daytype_baseline = 4,694
network_hour_daytype_baseline = 48
current_sensor_activity = 134
spatial_activity_cache = 0
```

## 11. Pass / Fail 判定

PASS：预期 UI、状态、请求边界、Console、build/tests 与数据完整性全部满足。

FAIL：出现 crash/blank page、stale journey、duplicate POST、fake crowd/route、技术错误
泄露、keyboard trap、横向溢出、测试失败或持久数据变化。记录复现步骤，不以扩大
产品 scope 的方式掩盖。

NOT RUN：环境不具备条件；必须写明原因，不能推测 PASS。

## 12. 未来 deployed acceptance 增补

Phase 6B 仍是本地验收。公开部署后必须另外验证：

- HTTPS 与 public domain；
- production CORS；
- production environment variables；
- geolocation 在 HTTPS 下的真实权限流程；
- cloud PostgreSQL/PostGIS availability；
- public Mapbox token 的 URL/domain restriction；
- public frontend、backend health 与真实 walking request 的端到端可达性。

这些项目本阶段不实现，当前结果必须保持 `NOT RUN`，直到 public deployment 存在。
