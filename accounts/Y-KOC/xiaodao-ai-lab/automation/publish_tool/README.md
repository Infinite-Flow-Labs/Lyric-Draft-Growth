# X 定时发帖工具（uv + Python）

通过 `chrome-devtools-mcp` 自动执行 X 定时发帖：

- 从指定目录读取 `post.txt` 和 `post.jpg`
- 通过参数指定定时发布时间
- 自动打开 X 发帖页、填充内容、上传图片、设置定时并提交
- 支持通过 CSV 按账号名自动定位比特浏览器窗口

## 环境要求

- `uv` >= 0.8
- 已安装 Chrome / 比特浏览器
- 可访问 X（`x.com`）

## 安装依赖

```bash
uv sync
```

## 目录准备

`--dir` 目录下必须存在：

- `post.txt`
- `post.jpg`

## CSV 账号映射表

项目根目录已提供模板：

- `accounts_bitbrowser.csv`

格式：

```csv
account,browser_id,bit_port,note
x_account_1@example.com,replace_with_browser_id,54345,示例备注
```

字段说明：

- `account`：你用于检索的账号名（邮箱/用户名都可以）
- `browser_id`：比特浏览器窗口 ID
- `bit_port`：比特本地 API 端口（默认通常是 `54345`）
- `note`：备注（可选）

## 用法

### 1) 直接指定 browser-url（已有调试地址）

```bash
uv run x-schedule-post \
  --dir /absolute/path/to/post-folder \
  --time "2026-03-12 20:30" \
  --timezone "Asia/Shanghai" \
  --browser-url "http://127.0.0.1:64950"
```

### 2) 按 CSV 账号名自动连接比特窗口（推荐）

```bash
uv run x-schedule-post \
  --dir /absolute/path/to/post-folder \
  --time "2026-03-12 20:30" \
  --timezone "Asia/Shanghai" \
  --accounts-csv ./accounts_bitbrowser.csv \
  --account "x_account_1@example.com"
```

执行时会自动调用：

- `http://127.0.0.1:<bit_port>/browser/open`

并拿到对应窗口的调试地址。

### 3) 不用 CSV，直接用比特窗口 ID

```bash
uv run x-schedule-post \
  --dir /absolute/path/to/post-folder \
  --time "2026-03-12 20:30" \
  --timezone "Asia/Shanghai" \
  --bit-browser-id "你的browser_id" \
  --bit-api-port 54345
```

## 常用参数

- `--dry-run`：执行到最后一步前停止（不点击最终发布）
- `--allow-immediate-post`：允许最终按钮不是“Schedule/定时”时也点击（默认关闭）
- `--headless`：无头模式运行
- `--login-timeout-minutes <n>`：首次登录等待超时，默认 `8`
- `--bit-open-timeout-seconds <n>`：比特 `/browser/open` 调用超时，默认 `10`

## 首次使用建议

1. 先使用 `--dry-run` 验证流程。
2. 确认比特浏览器窗口已打开。
3. 再去掉 `--dry-run` 执行真实定时发布。

## 注意

- X 页面结构可能变化，若脚本提示找不到控件，需要更新匹配规则。
- 发布时间请至少晚于当前时间 2 分钟。
