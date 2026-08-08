# CalmWay 当前版本测试流程

本文档供团队成员在本地克隆 CalmWay 仓库后，对当前版本执行完整测试。当前项目是一个可运行的大学实践原型，技术栈如下：

- 前端：React、Vite、TypeScript
- 后端：Python、FastAPI
- 测试：pytest

当前版本已实现 React 前端、FastAPI 后端及前后端调用。页面使用临时模拟路线数据，可以显示 LOW、HIGH 感官等级和推荐路线，也已实现英文表单验证及友好的接口失败提示。

## 1. 环境要求

开始前，请确认电脑已安装：

- Node.js
- npm
- Python 3.x
- Git

React 和 Vite 会通过项目依赖安装，不需要全局安装。

## 2. 启动后端

在项目根目录打开 Windows PowerShell，然后执行：

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

后端预期地址：

```text
http://127.0.0.1:8000
```

在浏览器中访问健康检查地址：

```text
http://127.0.0.1:8000/health
```

预期响应：

```json
{"status":"ok"}
```

Swagger 接口页面：

```text
http://127.0.0.1:8000/docs
```

## 3. 启动前端

保持后端运行，另开一个 Windows PowerShell 窗口，从项目根目录执行：

```powershell
cd frontend
npm install
npm run dev
```

如果 PowerShell 阻止运行 `npm.ps1`，请改用：

```powershell
npm.cmd install
npm.cmd run dev
```

前端预期地址：

```text
http://localhost:5173
```

## 4. 前端手动测试

| 编号 | 测试步骤 | 预期结果 |
| --- | --- | --- |
| TC01 | Origin 和 Destination 均留空，点击 `Find Routes`。 | 同时显示 `Origin is required.` 和 `Destination is required.`，且不发送路线请求。 |
| TC02 | 只填写 Origin，Destination 留空，然后点击 `Find Routes`。 | 显示 `Destination is required.`，且不发送路线请求。 |
| TC03 | 只填写 Destination，Origin 留空，然后点击 `Find Routes`。 | 显示 `Origin is required.`，且不发送路线请求。 |
| TC04 | Origin 输入 `Flinders Street Station`，Destination 输入 `State Library Victoria`，点击 `Find Routes`。 | 至少显示两张路线卡片。Route A 显示 1.2 km、15 min、LOW 和 Recommended；Route B 显示 1.0 km、12 min 和 HIGH。 |
| TC05 | Origin 输入 `Melbourne Central`，Destination 输入 `Federation Square`，点击 `Find Routes`。 | 界面保持正常，并成功加载路线结果。 |

TC04 和 TC05 返回的路线都是当前版本的临时模拟结果，并非真实路线。当前后端虽然接收 Origin 和 Destination，但返回结果尚未根据这些输入变化。

## 5. 前后端联通测试

使用 Chrome 开发者工具检查请求：

1. 按 `F12` 打开开发者工具。
2. 选择 `Network` 面板。
3. 在页面填写有效的 Origin 和 Destination。
4. 点击 `Find Routes`。
5. 在请求列表中找到 `/api/routes`。

预期状态码为 `HTTP 200`。这说明以下流程正常：

```text
React 前端
  → HTTP 请求
  → FastAPI 后端
  → JSON 响应
  → React 渲染
```

## 6. Swagger API 测试

打开 `http://127.0.0.1:8000/docs`，分别展开并执行：

- `GET /health`
- `GET /api/routes`

两个接口都应返回 `HTTP 200`。其中 `/api/routes` 当前返回临时模拟路线 JSON，不代表真实路线或真实行人数据。

## 7. 自动化测试

在项目根目录执行：

```powershell
.\backend\.venv\Scripts\python.exe -m pytest
```

当前预期结果：

```text
3 passed
```

## 8. 前端生产构建测试

执行：

```powershell
cd frontend
npm run build
```

如果 PowerShell 阻止运行 `npm.ps1`，请使用：

```powershell
npm.cmd run build
```

预期结果是 Vite 生产构建成功，并且没有 TypeScript 错误。

## 9. API 异常测试

1. 在运行后端的 PowerShell 窗口按 `Ctrl + C` 停止后端。
2. 保持前端运行。
3. 输入有效的 Origin 和 Destination。
4. 点击 `Find Routes`。

页面应显示：

```text
Unable to load routes. Please try again.
```

页面不应崩溃，输入框和按钮仍应可以继续使用。浏览器控制台可以记录技术错误，但页面不会直接展示原始网络错误。

## 10. 当前测试结果

以下项目已在当前开发环境中检查通过：

- [x] 前端页面正常加载
- [x] Origin 和 Destination 输入正常
- [x] 表单英文验证正常
- [x] Route A 和 Route B 正常显示
- [x] LOW 和 HIGH 感官等级标记正常
- [x] Recommended 标记正常
- [x] React 与 FastAPI 通信正常
- [x] `/health` 正常
- [x] `/api/routes` 正常
- [x] Swagger 正常
- [x] pytest 显示 `3 passed`
- [x] Vite 生产构建通过
- [x] 后端关闭时前端错误提示正常

> 不同组员的电脑环境可能不同，因此每位组员在克隆仓库后，仍建议自己完整执行一次测试流程。
