# Windows Publish Kit (BitBrowser)

目标：多账号复用“云端生产 -> 本地Windows同步 -> BitBrowser自动发X”。

## 你每新增一个账号时
1. 在云端准备好账号目录（含 automation/publish_ready 输出）
2. 在本地复制一份 win_jobs 脚本，修改 `ACCOUNT_ROOT_WIN`、`REMOTE_ACCOUNT_ROOT`、`BIT_ACCOUNT`
3. 导入/创建4个任务：08:10 sync, 08:30/12:00/19:30 publish

## 文件说明
- sync_publish_ready.ps1：从云端拉当天 publish_ready
- publish_slot.ps1：发布指定 slot
- register_tasks.ps1：一键创建 Windows 计划任务
- accounts_bitbrowser.csv.example：BitBrowser 账号映射模板
- profile.env.example：每个账号一份配置

## Runbook（故障排查）
### Step 1（标准第一步）：直跑可见命令
当任务计划显示成功/失败不一致，或你没看到浏览器动作时，先不要猜，直接手动直跑一条发布命令看完整日志。

```powershell
cd "<ACCOUNT_ROOT_WIN>\\automation\\publish_tool"
& "<PYTHON_EXE>" -m x_schedule_post.cli `
  --dir "<ACCOUNT_ROOT_WIN>\\automation\\publish_ready\\<YYYY-MM-DD>\\slot_03" `
  --time "<YYYY-MM-DD> 19:30" `
  --timezone "Asia/Shanghai" `
  --accounts-csv "<ACCOUNT_ROOT_WIN>\\automation\\win_jobs\\accounts_bitbrowser.csv" `
  --account "<BIT_ACCOUNT>"
```

判定标准：
- 能看到 `CSV匹配账号`、`已通过比特API获取调试地址`、`上传 post.jpg`、`点击最终定时发布按钮` 等关键日志。
- 若直跑成功而任务计划失败，优先检查任务运行身份、profile.env路径、PYTHON_EXE路径与SSH免密状态。
