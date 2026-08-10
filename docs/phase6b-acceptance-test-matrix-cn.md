# CalmWay Phase 6B 验收测试矩阵

## 说明

- `历史 AC` 指 `docs/acceptance-criteria.md` 或 immutable backend handoff 中已有的要求。
- `Phase 6B robustness check` 是本阶段新增的产品稳健性检查，不冒充历史 Kanban AC。
- 下方第一张表保留 audit-first 的初始 `NOT RUN` 登记快照；实际执行后的权威结果在文末 `最终执行结果`，只有取得证据后才标记 `PASS` 或 `FAIL`。
- immutable `handoff/` 目录不修改。

| ID | Category | Scenario | Precondition | Steps | Expected result | Test type | Result | Evidence / test reference |
|---|---|---|---|---|---|---|---|---|
| AC-NORMAL-01 | 历史 AC / 正常流程 | 完整 Home 到 Home 旅程 | 控制的有效地点和路线响应 | Home → Search → Options → View map → Depart → Navigation → Summary → End | 全流程可用，无崩溃 | Browser | NOT RUN | 待验证 |
| AC-NORMAL-02 | Phase 6B robustness check | 第二次规划 | 已完成一段旅程 | 返回 Home 后再次进入 Search | 无旧地点、路线、选中路线或 alert acknowledgement | Browser | NOT RUN | 待验证 |
| AC-STORY-11 | 历史 AC | US 1.1 路线比较 | 有 1–3 条可用路线和 crowd 数据 | 选择起终点与 tolerance 后比较 | 路线和可用 crowd 表示正确 | Browser + pytest | NOT RUN | 待验证 |
| AC-STORY-12 | 历史 AC | US 1.2 后端排名 | 控制的路线 crowd 数据 | 请求 walking routes | 使用权威排名而非默认最短路线 | Pytest | NOT RUN | 待验证 |
| AC-STORY-13 | 历史 AC | US 1.3 周期性导航重评估 | 正常 Navigation | 检查是否按最新窗口周期重评估/重路由 | 如未实现必须诚实标记 | Scope audit | NOT RUN | 待验证 |
| AC-SEARCH-01 | Phase 6B robustness check | 缺少 origin | Search 已打开 | 只选 destination 后提交 | 不 POST；显示 origin required | Browser | NOT RUN | 待验证 |
| AC-SEARCH-02 | Phase 6B robustness check | 缺少 destination | Search 已打开 | 只选 origin 后提交 | 不 POST；显示 destination required | Browser | NOT RUN | 待验证 |
| AC-SEARCH-03 | Phase 6B robustness check | 两者都缺少 | Search 已打开 | 直接提交 | 不 POST；两个字段均有简洁提示 | Browser | NOT RUN | 待验证 |
| AC-SEARCH-04 | Phase 6B robustness check | 文本未选 suggestion | Search 已打开 | 输入完整文本但不选择后提交 | 不使用假坐标；要求选择 suggestion | Browser | NOT RUN | 待验证 |
| AC-SEARCH-05 | Phase 6B robustness check | 编辑已选地点 | 已选结构化地点 | 修改输入文本后提交 | 旧坐标立即失效，不 POST | Browser | NOT RUN | 待验证 |
| AC-SEARCH-06 | Phase 6B robustness check | 清除已选地点 | 已选结构化地点 | 点击 Clear 后提交 | 结构化选择失效，不 POST | Browser | NOT RUN | 待验证 |
| AC-SEARCH-07 | Phase 6B robustness check | 相同起终点 | 两字段可选相同地点 | 选择后提交 | 受控结果；无崩溃、假路线或技术错误 | Browser | NOT RUN | 待验证 |
| AC-SEARCH-08 | Phase 6B robustness check | 很短查询 | Search 已打开 | 输入少于最小长度的文字 | 不发 suggestion 请求；表单仍可用 | Browser | NOT RUN | 待验证 |
| AC-SEARCH-09 | Phase 6B robustness check | 无匹配地点 | Search API 返回空 | 输入查询 | 显示简洁无结果提示，无崩溃 | Browser | NOT RUN | 待验证 |
| AC-SEARCHBOX-01 | Phase 6B robustness check | debounce 与最小长度 | 可记录 Search Box 请求 | 输入短/长查询 | 300ms debounce 与最小 3 字符保持 | Browser + source | NOT RUN | 待验证 |
| AC-SEARCHBOX-02 | Phase 6B robustness check | stale suggestion race | 第一请求延迟、第二请求较快 | 快速改变查询 | 取消/忽略旧响应，只显示最新建议 | Browser | NOT RUN | 待验证 |
| AC-SEARCHBOX-03 | Phase 6B robustness check | 键盘建议选择 | 建议列表可见 | Arrow Down/Up/Enter | active descendant 与选择正确 | Keyboard browser | NOT RUN | 待验证 |
| AC-SEARCHBOX-04 | Phase 6B robustness check | 鼠标建议选择 | 建议列表可见 | 点击建议 | retrieve 成功并建立结构化地点 | Browser | NOT RUN | 待验证 |
| AC-SEARCHBOX-05 | Phase 6B robustness check | 清除使 selection 失效 | 已选地点 | Clear | selected 状态和旧坐标均清除 | Browser | NOT RUN | 待验证 |
| AC-GEO-01 | Phase 6B robustness check | 定位成功 | 控制 geolocation success | Use my location | 显示 Current location selected | Browser | NOT RUN | 待验证 |
| AC-GEO-02 | Phase 6B robustness check | 权限拒绝 | 控制 code 1 | Use my location | 权限提示受控且可手动输入 | Browser | NOT RUN | 待验证 |
| AC-GEO-03 | Phase 6B robustness check | 位置不可用 | 控制 code 2 | Use my location | unavailable 提示受控 | Browser | NOT RUN | 待验证 |
| AC-GEO-04 | Phase 6B robustness check | 定位超时 | 控制 code 3 | Use my location | timeout 提示受控 | Browser | NOT RUN | 待验证 |
| AC-GEO-05 | Phase 6B robustness check | 浏览器不支持 | 移除 geolocation | Use my location | unsupported 提示受控 | Browser | NOT RUN | 待验证 |
| AC-GEO-06 | Phase 6B robustness check | 定位中重复/保留状态 | 已有手动 origin；定位 pending/fail | 快速双击并编辑 destination | 单次定位；提交禁用；destination 可编辑；失败保留 origin | Browser | NOT RUN | 待验证 |
| AC-LOADING-01 | Phase 6B robustness check | 路线请求 pending | 有效表单、延迟响应 | 提交 | 按钮禁用并显示 Finding walking routes... | Browser | NOT RUN | 待验证 |
| AC-LOADING-02 | Phase 6B robustness check | 路线双提交 | 有效表单、延迟响应 | 快速重复提交 | 只有一个 walking POST | Browser | NOT RUN | 待验证 |
| AC-ERROR-01 | Phase 6B robustness check | backend unavailable + retry | 第一次 network failure、第二次成功 | 提交、编辑/重试 | 页面保留；错误清晰；重试成功；无假路线 | Browser | NOT RUN | 待验证 |
| AC-ERROR-02 | Phase 6B robustness check | Mapbox upstream error | 控制 API 502 | POST walking | 后端和前端均返回 sanitized error | Browser + pytest | NOT RUN | 待验证 |
| AC-ERROR-03 | Phase 6B robustness check | Mapbox timeout | 控制 timeout | POST walking | timeout 不泄露内部细节 | Pytest | NOT RUN | 待验证 |
| AC-ERROR-04 | Phase 6B robustness check | zero routes | 控制空 routes | 路线正规化 | 受控 unavailable；不生成假路线 | Pytest | NOT RUN | 待验证 |
| AC-ERROR-05 | Phase 6B robustness check | malformed route candidate | 控制坏 geometry/字段 | 路线正规化 | 丢弃坏候选；全坏则受控失败 | Pytest | NOT RUN | 待验证 |
| AC-ERROR-06 | Phase 6B robustness check | malformed backend response | 前端收到坏 contract | 提交 Search | 留在 Search，显示统一用户错误，无崩溃 | Browser | NOT RUN | 待验证 |
| AC-ERROR-07 | Phase 6B robustness check | 缺少 backend Mapbox token | 控制 configuration error | POST walking | 503 sanitized；token 不泄露 | Pytest | NOT RUN | 待验证 |
| AC-DB-01 | 历史 AC-B24 / Phase 6B robustness check | DB/crowd failure | mock spatial/ranking 抛 DB error | 评估 route/API | 失败传播为 server error，不转 LOW/CLEAR/NO_DATA/0，不向用户泄露 | Pytest + Browser | NOT RUN | 待验证 |
| AC-CROWD-01 | 历史 AC-B11/B24 | Options insufficient data | 路线 crowd coverage 不足 | 打开 Options | 路线/距离/时间/map 可见；无 fake level/recommendation | Browser + pytest | NOT RUN | 待验证 |
| AC-CROWD-02 | Phase 6B robustness check | Navigation insufficient data | 选中 insufficient route | Depart | 路线/首 maneuver/unavailable 可见；无 ALERT/CLEAR/alternative | Browser | NOT RUN | 待验证 |
| AC-CROWD-03 | Phase 6B robustness check | ALERT 无 eligible alternative | 控制 alert route only | Depart | alert 与 Continue 显示；无 alternative button | Browser + pytest | NOT RUN | 待验证 |
| AC-CROWD-04 | Phase 6B robustness check | ALERT 有 eligible alternative | 控制两条合格路线 | Depart | alternative button 可用 | Browser + pytest | NOT RUN | 待验证 |
| AC-CROWD-05 | Phase 6B robustness check | CLEAR state | 控制 CLEAR | Depart | 显示 no alert triggered；无假 alert | Browser + pytest | NOT RUN | 待验证 |
| AC-CROWD-06 | Phase 6B robustness check | alternative switch | ALERT + eligible existing route | 点击 alternative | 使用已有 route，地图/距离/时间/指令更新；无新请求 | Browser | NOT RUN | 待验证 |
| AC-DIRECT-01 | Phase 6B robustness check | 直接 `/home` | 新 document/context | 打开 URL | Home 正常 | Browser | NOT RUN | 待验证 |
| AC-DIRECT-02 | Phase 6B robustness check | 直接 `/routes/search` | 新 document/context | 打开 URL | Search 正常 | Browser | NOT RUN | 待验证 |
| AC-DIRECT-03 | Phase 6B robustness check | 直接 `/routes/options` | 无 journey state | 打开 URL | 受控空状态/恢复路径；无崩溃 | Browser | NOT RUN | 待验证 |
| AC-DIRECT-04 | Phase 6B robustness check | 直接 `/navigation` | 无 journey state | 打开 URL | 受控空状态/恢复路径；无崩溃 | Browser | NOT RUN | 待验证 |
| AC-DIRECT-05 | Phase 6B robustness check | 直接 `/arrival` | 无 journey state | 打开 URL | 受控空状态/恢复路径；无崩溃 | Browser | NOT RUN | 待验证 |
| AC-REFRESH-01 | Phase 6B robustness check | refresh Home | Home 已打开 | reload | Home 正常 | Browser | NOT RUN | 待验证 |
| AC-REFRESH-02 | Phase 6B robustness check | refresh Search | Search 已打开 | reload | Search 正常 | Browser | NOT RUN | 待验证 |
| AC-REFRESH-03 | Phase 6B robustness check | refresh Options | 有内存 journey 后 reload | reload | 受控空状态；无坏 map/TypeError | Browser | NOT RUN | 待验证 |
| AC-REFRESH-04 | Phase 6B robustness check | refresh Navigation | 有 selected route 后 reload | reload | 受控空状态；无坏 map/TypeError | Browser | NOT RUN | 待验证 |
| AC-REFRESH-05 | Phase 6B robustness check | refresh Arrival | 有 summary 后 reload | reload | 受控空状态；无 TypeError | Browser | NOT RUN | 待验证 |
| AC-HISTORY-01 | Phase 6B robustness check | Home → Search → browser Back | 正常 Home | CTA 后 Back | 返回 Home | Browser | NOT RUN | 待验证 |
| AC-HISTORY-02 | Phase 6B robustness check | Options → Edit search | 已有搜索结果 | Edit search | Search 恢复当前内存地点与 preference | Browser | NOT RUN | 待验证 |
| AC-HISTORY-03 | Phase 6B robustness check | Navigation → browser Back | 已 Depart | Back | Options 正常且 route state 保留 | Browser | NOT RUN | 待验证 |
| AC-HISTORY-04 | Phase 6B robustness check | Summary → browser Back | Summary 已打开 | Back | Navigation 恢复且不崩溃 | Browser | NOT RUN | 待验证 |
| AC-HISTORY-05 | Phase 6B robustness check | reset 后 browser Back/Forward | End navigation 已执行 | Back/Forward | 旧 protected route 只显示受控恢复状态，不复活旧 journey | Browser | NOT RUN | 待验证 |
| AC-BUTTON-01 | Phase 6B robustness check | 普通内部按钮 | 正常各页 | CTA/Edit/View/Depart/Nav back/End overview/End navigation | 无 dead button 或缺失页面 | Browser | NOT RUN | 待验证 |
| AC-BUTTON-02 | Phase 6B robustness check | Crowd Alert 按钮 | 控制 ALERT fixtures | Continue / Start alternative | 两个动作按状态正确工作 | Browser | NOT RUN | 待验证 |
| AC-REPEAT-01 | Phase 6B robustness check | 重复 Use my location | pending geolocation | 快速点击 | 只有一个请求 | Browser | NOT RUN | 待验证 |
| AC-REPEAT-02 | Phase 6B robustness check | 重复 Depart | Options 已打开 | 快速点击 | route/context 不损坏，无额外 API | Browser | NOT RUN | 待验证 |
| AC-REPEAT-03 | Phase 6B robustness check | 重复 End route overview | Navigation 已打开 | 快速点击 | 单次安全导航，无 API | Browser | NOT RUN | 待验证 |
| AC-REPEAT-04 | Phase 6B robustness check | 重复 End navigation | Summary 已打开 | 快速点击 | reset 幂等且 Home 正常，无 API | Browser | NOT RUN | 待验证 |
| AC-MAP-01 | Phase 6B robustness check | 缺少/无效 frontend Mapbox token | 不改真实 env 的受控构建 | 打开 Search | controls 可用；map/place search 简洁 unavailable；不显示 token | Browser | NOT RUN | 待验证 |
| AC-MAP-02 | Phase 6B robustness check | invalid route geometry | 控制坏 backend contract/组件输入 | 提交/渲染 | 不画坏 map；显示受控错误；无崩溃 | Browser + source | NOT RUN | 待验证 |
| AC-MAP-03 | Phase 6B robustness check | map init/draw failure | 控制 map error | 打开 Search/Options | 页面 controls/card 保持；显示 Map unavailable | Browser + source | NOT RUN | 待验证 |
| AC-COPY-01 | Phase 6B robustness check | 用户 error copy audit | 触发所有控制错误 | 检查可见文字 | 无 HTTP/FastAPI/PostGIS/token/GeoJSON/stack/enums | Browser + source | NOT RUN | 待验证 |
| AC-COPY-02 | Phase 6B robustness check | loading copy audit | 触发 locate/search/retrieve/route loading | 检查可见文字 | 使用 final-user copy；无 phase/mock/preview/backend wording | Browser + source | NOT RUN | 待验证 |
| AC-A11Y-01 | Phase 6B robustness check | 全流程 Tab/Enter | 正常/alert 流程 | 键盘遍历交互项 | 主要动作可达，无 keyboard trap | Keyboard browser | NOT RUN | 待验证 |
| AC-A11Y-02 | Phase 6B robustness check | 名称与非颜色语义 | 各 crowd/error 状态 | 检查 role/name/text | alert/unavailable 不只依赖颜色；明显名称存在 | Browser + source | NOT RUN | 待验证 |
| AC-DESKTOP-01 | Phase 6B robustness check | 1440×900 全页面 | controlled normal/alert data | Home/Search/Options/Nav/Summary | 无横向溢出或裁切；map/card/CTA 可用 | Browser | NOT RUN | 待验证 |
| AC-MOBILE-01 | Phase 6B robustness check | 390×844 全页面 | controlled normal/alert data | Home/Search/Options/Nav/Summary | 无横向溢出或裁切；建议/卡片/CTA 可用 | Browser | NOT RUN | 待验证 |
| AC-CONSOLE-01 | Phase 6B robustness check | 正常旅程 console | controlled normal route | 跑完整流程 | 无未捕获应用异常/重复失败 | Browser | NOT RUN | 待验证 |
| AC-NETWORK-01 | Phase 6B robustness check | 请求边界 | 正常 + alternative 流程 | 记录 fetch/network | Search 仅 1 POST；其余动作无 POST/前端 Directions | Browser | NOT RUN | 待验证 |
| AC-BUILD-01 | Phase 6B robustness check | frontend build | 当前 working tree | `npm.cmd run build` | 成功；既有 bundle warning 可接受 | Command | NOT RUN | 待验证 |
| AC-BACKEND-01 | 历史 backend AC | 完整 backend regression | 当前 working tree | `python -m pytest` | 0 failed；记录 passed/skipped | Pytest | NOT RUN | 待验证 |
| AC-DATABASE-01 | Phase 6B robustness check | 数据库完整性 | local DB 可用时 | read-only count/check | 既有行数不变；无持久测试数据 | Command / DB | NOT RUN | 待验证 |
| AC-DEPLOY-01 | Phase 6B robustness check | deployed-only acceptance | 尚未部署 | HTTPS/domain/CORS/env/token restriction/cloud DB | 本地 Phase 6B 不伪造结果，部署后执行 | Deployed manual | NOT RUN | 尚未部署 |

## 最终执行结果（权威）

共记录 **77** 个 scenario：**75 PASS / 1 FAIL / 1 NOT RUN**。唯一 FAIL 是历史
User Story 1.3 中尚未实现的周期性 live navigation 评估，不是本阶段引入的回归；
部署检查因尚无 public deployment 而保持 NOT RUN。

| Scenario IDs | Final result | Evidence / test reference |
|---|---|---|
| Final: AC-NORMAL-01–02 | PASS | Controlled Edge journey：Home → Search → Options → Navigation → Summary → Home；第二次 Search 无 stale state并成功规划 |
| Final: AC-STORY-11–12 | PASS | Controlled numeric/insufficient browser fixtures；`tests/test_routes_api.py`；`tests/test_route_crowd_ranking_service.py` |
| Final: AC-STORY-13 | **FAIL** | Scope/source audit：只在 0 m 计算 initial decision；无 live progress、周期性新窗口评估或自动 rerouting；历史 AC 保持原文 |
| Final: AC-SEARCH-01–09 | PASS | Controlled Edge validation audit：0 incomplete POST；edited/cleared selections 失效；short/no-match/same-location 均受控 |
| Final: AC-SEARCHBOX-01–05 | PASS | Controlled Edge timing/race audit：300 ms、minimum 3、old request aborted/ignored、Arrow Up/Down/Enter 与 mouse selection |
| Final: AC-GEO-01–06 | PASS | Controlled Edge geolocation success/code 1/code 2/code 3/unsupported/pending fixtures；duplicate count = 1；manual origin preserved |
| Final: AC-LOADING-01–02 | PASS | Controlled delayed walking response；按钮 disabled、`Finding walking routes...`、rapid double submit = 1 POST；Phase 6B in-flight guard regression |
| Final: AC-ERROR-01–07 | PASS | Controlled browser network/502/500/malformed fixtures；`tests/test_mapbox_directions_client.py`；`tests/test_walking_routing_service.py`；`tests/test_routes_api.py` |
| Final: AC-DB-01 | PASS | `test_database_failure_is_propagated_and_not_converted_to_no_data`；新增 `test_crowd_database_failure_is_not_converted_or_exposed`；browser 500 copy sanitized |
| Final: AC-CROWD-01–06 | PASS | Controlled INSUFFICIENT_DATA/ALERT/CLEAR browser flows；eligible/no-eligible alternative；existing route switch；crowd/ranking/alert pytest suites |
| Final: AC-DIRECT-01–05 | PASS | Fresh-document Edge direct-open on all five routes；existing safe empty-state guards；0 blank/exception |
| Final: AC-REFRESH-01–05 | PASS | Edge reload on all five routes；in-memory protected state deterministically becomes safe empty state |
| Final: AC-HISTORY-01–05 | PASS | Edge Back/Forward、Edit search retention、Navigation/Summary Back、reset 后 protected route safe recovery |
| Final: AC-BUTTON-01–02 | PASS | Controlled normal/ALERT flows exercised all listed internal actions；all destinations exist；no fake menu |
| Final: AC-REPEAT-01–04 | PASS | Controlled rapid actions：geolocation once；Depart/End overview/End navigation keep valid context and add no API work |
| Final: AC-MAP-01–03 | PASS | Separate empty-token Vite mode；controlled style 503；malformed contract；fallback visible、controls/card independent、token not displayed |
| Final: AC-COPY-01–02 | PASS | Visible error/loading source + browser audit；no banned internal term；final copy includes Locating/Search/Confirm/Walking loading states |
| Final: AC-A11Y-01–02 | PASS | Edge Tab/Enter, suggestion arrows, radio arrows；native links/buttons；labels/legend/roles/text states；no keyboard trap observed |
| Final: AC-DESKTOP-01 | PASS | Edge 1440×900：Home/Search/Options/Navigation/Summary；0 horizontal overflow、0 clipped primary actions |
| Final: AC-MOBILE-01 | PASS | Edge 390×844：five pages + suggestions；0 horizontal overflow、0 clipped actions |
| Final: AC-CONSOLE-01 | PASS | Normal full journey：0 console error、0 uncaught exception；controlled failure logs were single sanitized app messages |
| Final: AC-NETWORK-01 | PASS | Normal Search = 1 walking POST；all later actions/alternative = 0 extra；frontend Directions = 0 |
| Final: AC-BUILD-01 | PASS | `npm.cmd run build` passed；only accepted Mapbox bundle-size warning |
| Final: AC-BACKEND-01 | PASS | Full regression：**251 passed, 8 skipped, 0 failed** |
| Final: AC-DATABASE-01 | PASS | Read-only audit exactly matched 1,182,041 / 4,694 / 48 / 134 / 0 reference counts |
| Final: AC-DEPLOY-01 | **NOT RUN** | No public deployment exists；HTTPS/domain/production CORS/env/token restriction/cloud DB are explicitly deferred |

## Phase 6B defects

| Defect | Reproduction | Fix | Re-test |
|---|---|---|---|
| Rapid same-task route submit produced two identical walking POSTs before React applied `disabled` | Delayed controlled route response + immediate double click recorded 2 POSTs | Added a form-local in-flight ref guard; no global debounce or API change | Same test records exactly 1 POST and final loading copy |
| Missing frontend Mapbox token claimed the user could still plan a route although required destination search was unavailable | Separate Vite mode with empty token showed contradictory map/place messages | Fallback now truthfully says map and place search are unavailable | Empty-token browser re-test passes; form stays mounted; no token shown |
