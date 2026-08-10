# Current Activity 安全刷新端点

## 端点与返回值

生产后端提供：

```text
POST /api/v1/internal/refresh-current-activity
Authorization: Bearer <REFRESH_SECRET>
```

成功响应只包含安全的运行摘要：

```json
{
  "status": "ok",
  "updated": 134
}
```

`updated` 是现有 refresh service 返回的 `current_rows_written`，不是未经验证
的 City API 或数据库内部信息。

## Bearer 认证与环境变量

`REFRESH_SECRET` 只从后端进程环境读取。缺少或格式错误的 Authorization
header 返回 401，错误 secret 返回 403；若部署没有配置
`REFRESH_SECRET`，端点 fail closed 并返回 503。比较使用 Python
`secrets.compare_digest`，响应和日志都不包含期望值或提交值。

Vercel 后端的必需生产变量现在是：

- `DATABASE_URL`
- `MAPBOX_ACCESS_TOKEN`
- `FRONTEND_ORIGINS`
- `REFRESH_SECRET`

应为 `REFRESH_SECRET` 生成高熵、独立且可轮换的值，分别配置到所需的
Vercel 环境；不要把真实值写入 `.env.example`、命令历史或仓库。

## 现有刷新逻辑复用

端点直接调用既有 `CurrentActivityRefreshService.refresh()`，使用当前 UTC
时间和 `dry_run=False`。City minute snapshot、转换、raw minute 去重写入、
historical baseline 比较与 `current_sensor_activity` 事务替换逻辑没有复制或
修改。任何 City API、数据库或意外异常统一转换为不含内部细节的 503 响应。

## Vercel / serverless 行为

刷新只在收到通过认证的 POST 请求时执行。FastAPI startup 不会调用它，且
没有新增 thread、scheduler、cron、后台循环或本地持久文件依赖。它是一个
普通同步 Vercel Function 请求；service 和 HTTP client 只可能在 warm
instance 内复用，正确性不依赖实例常驻。

## 后续 GitHub Actions 调用

Phase 7D-2 将配置 GitHub Actions 每 15 分钟发起一次带 Bearer header 的
POST，并把调用 secret 保存在 GitHub Actions Secrets。本阶段明确不创建
workflow、不配置 schedule，也不部署或调用生产端点。

## 后续手工生产验证步骤

部署和配置完成后，在 PowerShell 中安全输入 secret，避免把值写进命令历史：

```powershell
$secureRefreshSecret = Read-Host "Refresh secret" -AsSecureString
$plainRefreshSecret = [Net.NetworkCredential]::new(
  "", $secureRefreshSecret
).Password
try {
  Invoke-RestMethod `
    -Method Post `
    -Uri "https://calmway-backend.vercel.app/api/v1/internal/refresh-current-activity" `
    -Headers @{ Authorization = "Bearer $plainRefreshSecret" }
} finally {
  Remove-Variable plainRefreshSecret, secureRefreshSecret
}
```

期望得到 `status=ok` 和非负 `updated`。随后检查 Vercel 日志只包含状态和
必要的运行诊断，不含 Authorization header、secret、数据库 URL 或原始异常。
再分别验证无 header 为 401、格式错误为 401、错误 secret 为 403；测试值也
不要写入脚本或仓库。
