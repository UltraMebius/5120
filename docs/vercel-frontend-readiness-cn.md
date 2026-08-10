# CalmWay Vercel 前端就绪说明

本文只记录现有 Vite/React 前端的 Vercel 部署准备。本阶段没有创建、关联或
部署 Vercel 项目，没有修改真实 `.env`，也没有改变产品流程。

## Vercel 前端目录

- 后续 Vercel 前端项目的 **Root Directory** 设置为 `frontend`。
- Framework Preset 使用自动检测的 Vite；Build Command 保持
  `npm run build`，输出目录保持 Vite 默认的 `dist`。
- `frontend/vercel.json` 位于该项目根目录，只配置 SPA rewrite。

## 生产环境变量

在 Vercel Preview/Production 环境分别配置：

| 变量 | 生产值与用途 |
| --- | --- |
| `VITE_API_BASE_URL` | `https://calmway-backend.vercel.app`，不带结尾 `/` |
| `VITE_MAPBOX_PUBLIC_TOKEN` | 浏览器可用的 Mapbox public token |

`VITE_HOME_ROUTE` 可不配置，现有默认值是 `/home`。现有 crowd-tolerance
Vite 变量也有项目默认值，并非本次部署必填项。

所有 `VITE_` 变量都会进入浏览器 bundle。因此只能在
`VITE_MAPBOX_PUBLIC_TOKEN` 中放 Mapbox public token，绝不能放后端
`MAPBOX_ACCESS_TOKEN`、Neon URL 或其他服务端 secret。生产后端 URL 只在
Vercel 环境变量和本文部署记录中出现，没有硬编码到应用源代码。

## API URL 决策

`frontend/src/config.ts` 使用 Vite 可在 build time 静态替换的完整
`import.meta.env.VITE_API_BASE_URL` 属性读取 API base URL，并移除一个结尾
`/`；`frontend/src/services/api.ts` 继续通过该配置请求
`/api/v1/routes/walking`。未设置变量时仍回退到
`http://localhost:8000`，所以本地前后端开发行为不变。

Mapbox 原有配置同样直接读取
`import.meta.env.VITE_MAPBOX_PUBLIC_TOKEN`。Vite 环境变量会在 build time
写入客户端 bundle，参考
[Vite 环境变量文档](https://vite.dev/guide/env-and-mode)。

部署前端取得实际域名后，还需在后端 Vercel 项目的
`FRONTEND_ORIGINS` 中加入该完整 origin，才能允许浏览器 CORS 请求；本阶段
不修改后端配置。

## SPA 路由与刷新

当前应用使用 `BrowserRouter`。Vercel 对 Vite SPA 的 deep link 不会默认
回退到入口文件，因此 `frontend/vercel.json` 使用官方最小配置，把未命中
静态文件的路径 rewrite 到 `/index.html`，URL 本身不改变：

```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

这使 `/home`、`/routes/search`、`/routes/options`、`/navigation` 和
`/arrival` 的直接访问/刷新先加载 React，再由 React Router 处理。依据：
[Vercel Vite SPA deep-link 文档](https://vercel.com/docs/frameworks/frontend/vite)。

JourneyContext 仍只保存在内存中，没有增加 localStorage 或持久化。刷新需要
journey state 的页面时，现有 Route Options、Navigation、Arrival guard 会
显示原有空状态/返回路径；SPA rewrite 只消除平台 404，不绕过这些 guard。

## 本地开发行为

- 真实 `frontend/.env` 保持忽略且不变。
- 未配置 `VITE_API_BASE_URL` 时继续请求 `http://localhost:8000`。
- Mapbox 继续只读取 `VITE_MAPBOX_PUBLIC_TOKEN`。
- 本地命令保持 `npm run dev`；生产检查保持 `npm run build`。

## 后续部署步骤（本阶段不执行）

1. 在 Vercel Dashboard 从相同 Git 仓库创建独立前端项目。
2. 将 Root Directory 精确设为 `frontend`，确认 Vite preset、
   `npm run build` 和 `dist` 输出目录。
3. 在目标 Preview/Production 环境设置 `VITE_API_BASE_URL` 和
   `VITE_MAPBOX_PUBLIC_TOKEN`；不要把 token 写入仓库。
4. 创建 Preview deployment 后，将 Preview frontend origin 加到对应后端
   `FRONTEND_ORIGINS`，再验证 route search、Mapbox 搜索/地图和 walking API。
5. 分别直接打开并刷新 `/home`、`/routes/search`、`/routes/options`、
   `/navigation`、`/arrival`，确认没有 Vercel 404，且依赖 journey state 的
   页面仍执行原有 guard。
6. Preview 验收通过后才进行 Production deployment；把正式前端 origin
   加入后端生产 `FRONTEND_ORIGINS` 并重复端到端验证。
