# CalmWay GitHub Actions 定时刷新

工作流 `.github/workflows/refresh-current-activity.yml` 每 15 分钟调用一次生产
current activity 刷新端点，也支持从 GitHub Actions 页面手动触发。

## 时间表与运行保护

- Cron：`7,22,37,52 * * * *`
- 时区：`Australia/Melbourne`
- 本地执行分钟：每小时第 7、22、37、52 分钟
- Job 最长运行 5 分钟；单次 HTTP 请求最长等待 180 秒
- 同一时间只运行一个 refresh；新运行不会取消已在执行的数据库刷新
- 不自动 retry；失败后等待下一次定时运行，或由维护者手动触发

GitHub 的 `schedule` 只会在默认分支运行，并使用默认分支的最新提交。因此必须
先让该 workflow 文件存在于仓库默认分支，定时刷新才会生效。

## Secret 与生产端点

在仓库 `Settings > Secrets and variables > Actions` 中创建唯一需要的
Repository secret：

```text
CALMWAY_REFRESH_SECRET
```

它的值必须与生产后端的 `REFRESH_SECRET` 一致，但不得写入 workflow、文档、
日志或仓库文件。工作流通过 Bearer header 调用：

```text
POST https://calmway-backend.vercel.app/api/v1/internal/refresh-current-activity
```

## 手动运行与成功验证

打开仓库的 `Actions` 页面，选择 `Refresh current activity`，再选择
`Run workflow`。成功时，run 和 `Refresh production current activity` step
均显示绿色，curl 输出安全响应 `status=ok` 和非负 `updated`。HTTP 非 2xx、
连接错误或 180 秒超时都会令 step 失败；工作流不会自动重试。

## 禁用

在 GitHub `Actions` 页面打开该 workflow，通过右上角菜单选择
`Disable workflow`。需要恢复时可选择 `Enable workflow`。也可以通过代码评审
移除 `schedule`，只保留 `workflow_dispatch`，从而暂停定时执行但保留手动调用。
