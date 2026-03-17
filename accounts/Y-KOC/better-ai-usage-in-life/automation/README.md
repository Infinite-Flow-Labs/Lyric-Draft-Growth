# xiaodao-ai-lab automation

## 目标流程
1. 每天 08:00 抓对标源到 `sources/YYYY-MM-DD/`
2. 从 source 提取 Top3 选题到 `topics/YYYY-MM-DD/`
3. 按模板产出 3 篇到 `content/YYYY-MM-DD/`
4. 09:30 / 13:30 / 19:30 定时发布，失败重试并记录日志

## 文件
- `daily_pipeline.py`：执行 1/2/3（基于 Nitter RSS）
- `publisher_playwright.py`：执行 4（X 自动定时发布）
- `save_storage_state.py`：首次人工登录后保存会话
- `config.json`：账号与调度配置

## 依赖
```bash
python3 -m pip install --user playwright
python3 -m playwright install chromium
```

## 首次登录（人工一次）
```bash
python3 save_storage_state.py --config config.json --headed
```
按提示在打开的浏览器里完成登录，回车后保存 `x-storage-state.json`。

## 每日跑内容流程
```bash
python3 daily_pipeline.py --config config.json --date 2026-03-07
```

## 发布（使用 storage_state）
```bash
python3 publisher_playwright.py --config config.json --date 2026-03-07
```

## 配置定时（crontab 示例，Asia/Shanghai）
```cron
# 08:00 抓源+选题+产文
0 8 * * * cd /root/.openclaw/agent-workspaces/growth-assistant/inbound_assets/xiaodao_benchmark_sources/accounts/xiaodao-ai-lab/automation && /usr/bin/python3 daily_pipeline.py --config config.json --date $(date +\%F) >> cron.log 2>&1

# 发布器常驻（每5分钟检查待发布任务）
*/5 * * * * cd /root/.openclaw/agent-workspaces/growth-assistant/inbound_assets/xiaodao_benchmark_sources/accounts/xiaodao-ai-lab/automation && /usr/bin/python3 publisher_playwright.py --config config.json --date $(date +\%F) >> cron.log 2>&1
```

> 说明：X 页面结构变化可能导致选择器失效；失败会记录到 `logs/`，可重跑。