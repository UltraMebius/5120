# CalmWay Phase 5B-1：路线前方人流警报决策引擎

## 为什么需要 Phase 5B-1

Phase 3E 已经为约每 50 米的路线样本生成点级人流结果，Phase 4 则负责整条候选路线的聚合和排序。Phase 5B-1 解决另一个独立问题：对于已经选择的路线，根据当前可用的样本数据，未来 300 米内是否出现足够连续的高于用户偏好的人流证据。

本阶段只返回纯领域决策，不显示警报界面，不选择替代路线，也不改变 Phase 4 排名。

## 不是实时 GPS 导航

服务接收调用方明确提供的 `current_progress_meters`。`0` 表示明确从路线起点进行静态评估，不代表系统通过 GPS 测到了用户位置。当前实现没有 `watchPosition`、持续定位、map matching、路线吸附、转弯进度、偏航、自动重规划或到达检测。

未来导航能力可以提供新的进度值。例如调用方明确传入 `150` 时，服务才会评估 `(150, 450]` 米；服务自身绝不推测进度。

## 300 米窗口

项目批准的 MVP 配置为：

```text
ROUTE_ALERT_LOOK_AHEAD_DISTANCE_M=300
ROUTE_ALERT_REQUIRED_CONSECUTIVE_SAMPLES=2
```

窗口边界为：

```text
sample distance > current progress
sample distance <= current progress + 300m
```

当前进度处的样本不属于“前方”，恰好在 300 米边界的样本会被包含。路线剩余不足 300 米时只评估真实剩余样本，包括范围内的终点，不补造样本。进度位于或超过终点时没有前方样本，结果为 `INSUFFICIENT_DATA / NO_SAMPLES_AHEAD`。

## 样本证据与连续规则

样本必须同时满足以下条件才是可用数值证据：

- `coverage_status` 为 `SUPPORTED` 或 `LIMITED`；
- `crowd_exposure_score` 是有效数值。

两种支持状态在 MVP 警报判断中都可用，但诊断计数分别保留。`NO_DATA` 不参与数值判断，绝不能转换为 0、LOW、安全或 CLEAR 证据。

`ALERT` 需要至少两个相邻路线样本都严格高于偏好阈值。相邻指 Phase 3D 保存的路线顺序中 index 连续。`NO_DATA`、没有数值的支持样本或等于/低于阈值的样本都会中断 streak，不能跳过中间样本把两端拼成连续证据。

两个样本规则用于减少单个孤立高值触发警报，是项目 MVP heuristic。约 50 米采样与“大约持续 100 米”的关系不是经过科学或用户研究验证的结论。

偏好阈值直接复用项目现有配置：

| UI 容忍度 | 内部偏好 | 阈值 |
|---|---|---:|
| LOW | `AVOID_BUSY` | 50 |
| MEDIUM | `PREFER_QUIETER` | 75 |
| HIGH | `FLEXIBLE` | 90 |

判断使用严格 `score > threshold`；等于阈值仍在偏好范围内。

## 三种决策

- `ALERT`：窗口内存在至少一个符合规则的连续 streak。
- `CLEAR`：至少有一个可用数值样本，但没有符合规则的 streak。它只表示“目前可用数据没有检测到触发条件”，不表示路线已经证明安全或不拥挤。
- `INSUFFICIENT_DATA`：窗口内没有任何可用数值样本，或根本没有前方样本。不能把它转成 CLEAR。

部分数据仍被诚实评估。例如 `60, NO_DATA, 70` 对 LOW 偏好没有连续 pair，因此是 CLEAR，但覆盖率和 NO_DATA 计数会说明支持不完整。`look_ahead_coverage_pct` 的分母是窗口内全部样本；`pct_above_preference_in_window` 的分母只包含可用数值样本。没有分母时返回 `null`，不制造 0。

## 确定性示例

```text
LOW threshold = 50

index 1: SUPPORTED 60
index 2: LIMITED   72
=> ALERT, trigger 1-2

index 1: SUPPORTED 60
index 2: NO_DATA
index 3: SUPPORTED 72
=> CLEAR, NO_DATA 中断 streak

index 1: SUPPORTED 50
index 2: SUPPORTED 70
=> CLEAR, 50 等于阈值且只有一个样本高于阈值
```

若第一个 streak 为 index 4、5、6，服务返回完整的 4-6；若后方还有另一个 qualifying streak，仍选择路线顺序中最先、最近的第一个。窗口最大暴露值可以继续描述整个窗口。

## 输出与 Phase 5B-2 边界

不可变结果包含决策、原因、偏好、阈值、进度、窗口、样本/支持/覆盖率诊断，以及 nullable 的 trigger 起止 index、距离、样本数、前两个暴露值和 trigger 最大值。它不包含假街道名、reverse geocoding、数据库错误或 GPS 元数据。

Phase 5B-2 才负责把结果接入 UI、决定警报呈现方式，并设计替代路线动作。Phase 5B-1 没有 modal、banner、toast、Crowd Alert screen、`Start lower-stimulation route` 或路线切换。

## 离线验证

运行纯单元测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_route_crowd_alert_service.py
```

运行受控三状态演示：

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_route_crowd_alert.py
```

两者都不访问 PostGIS、Mapbox、City API 或 GPS，也不写任何数据。真实 current materialisation 若没有可用覆盖，正确结果仍然可以是 `INSUFFICIENT_DATA`，不应为了演示而制造 ALERT。
