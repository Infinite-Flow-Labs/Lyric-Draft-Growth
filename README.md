# Growth Engine Pipeline

Infinite Flow Labs 的 AI 内容增长引擎。从信号采集到文章发布的全自动化 pipeline。

## 架构总览

```
信号采集 → 主题聚类 → 泳道路由 → 你审核选题 → 文章生成 → 配图 → 分发发布
  L0         L1          L1                      L2         L3      L4
```

整个系统做一件事：**从互联网上的 AI 领域信号中，自动筛选出值得写的话题，生成高质量文章并发布到 X**。

---

## 流水线详解

### L0 信号采集（pipeline/ingest/）

从 X/Twitter 和 Podcast 抓取原始内容。通过 Nitter RSS 订阅 130+ 个 AI 领域账号，抓取新推文和播客 episode。每条内容标准化为 `source_item.json`，提取标题、全文、发布时间、作者信息。

### L1 主题引擎（pipeline/engine/）

做四件事：过滤噪音 → 聚类成主题 → 选泳道 → 排名。

**过滤**：字数太少、没有可引用事实、太旧的信号直接过滤。

**聚类**：把讨论同一件事的信号归为一组。提到同一个具体产品名的归在一起；只共享"AI""Claude Code"这类泛词的不够，还需要额外证据（同一作者 / 6 小时内 / 发布关键词匹配）。22 个 AI 高频词被标记为"泛词"防止错误聚类。

**热度排名**：每条信号的热度分考虑 5 个因素——新鲜度、事实密度、发布信号、互动量（likes/转发/浏览，通过 fxtwitter API 自动获取）、发布者影响力等级（S 级 ×10、A 级 ×5、B 级 ×2、C 级 ×1）。

**同样一条内容，dotey（A 级）发出来的热度是无名账号的 5 倍，OpenAI（S 级）发的是 10 倍。叠加互动量差异，实际差距 10-20 倍。**

每个 topic 的优先级 = 声量 30% + 时效 30% + 跨源共振 20% + 新颖度 20%。

**泳道路由**：每个 topic 分配到 8 个泳道中最合适的一个，通过信号特征匹配。泳道均衡机制保证每个泳道最多占总数 1/4。

**审核**：产出按热度排序的选题清单，你选择哪些进入写作。

### L2 文章生成（pipeline/writer/）

1. **数据补充**（无 LLM）—— 从 URL 抓取 GitHub 数据（stars/forks）和产品页标题
2. **痛点提取**（Haiku）—— 找出读者最可能遇到的具体痛点，作为文章钩子
3. **文章生成**（Sonnet）—— 27K prompt → 完整文章
4. **质量门禁**（正则检测）—— 自动检测 12 种问题（AI 句式、防御否定、反问结尾、bare handle 等）
5. **修复循环**（Sonnet）—— 门禁不通过时自动修复，最多 5 轮
6. **格式化** —— 结构化 article_blocks + source_embed（X 引用卡片）+ 去 bold 标记

### L3 配图（pipeline/image/）

根据泳道自动匹配 8 种视觉风格。按文章 section 拆分，为每个 section 选图表类型，调用 baoyu-image-gen + KIE API 生成。1 张封面 + 最多 6 张 inline 图，插在每个 section 内容结束处。

| 泳道 | 配图风格 |
|------|---------|
| T01 发布解读 | 暖色手绘信息图 |
| T02 信号解码 | 信号解读卡（靛蓝/琥珀） |
| T03 结果证明 | ROI 证明板（绿/金） |
| T04 纠偏逆转 | 案例拆解（红/绿对比） |
| T05 对比筛选 | 数据仪表盘（蓝/白） |
| T06 能力交付 | 科技蓝图（暗底/蓝光） |
| T07 逆向观点 | 锐评海报（黑底/大字） |
| T08 信号转行动 | 行动手册（暖底/橙色） |

### L4 分发发布（pipeline/publish/）

按账号分配文章，通过比特浏览器 + x-schedule-post 自动操作 X Articles 编辑器：上传封面 → 输入标题 → 粘贴正文（自动切换引用/正文/小标题/列表样式）→ 插入 inline 图 → source_embed 渲染为引用卡片。

---

## 8 个内容泳道

| 泳道 | 写作角度 | 典型内容 |
|------|---------|---------|
| T01 发布解读 | 新产品发布 → 采用路径 → 谁该用 | "XX 发布了新功能，对你意味着什么" |
| T02 信号解码 | 外部信号 → 一个主论点 → 判断 | "这件事背后真正值得注意的是..." |
| T03 结果证明 | ROI 数字 → 证据链 → 成本收益 | "他用 XX 工具赚了多少" |
| T04 纠偏逆转 | 失败 → before/after → 教训 | "我们踩了坑，后来这样解决的" |
| T05 对比筛选 | 多选项 → 数据对比 → 推荐 | "A vs B vs C，哪个适合你" |
| T06 能力交付 | 功能 → 具体操作 → 步骤清单 | "手把手教你配置 XX" |
| T07 逆向观点 | 主流观点 → 反驳 → 重新定义 | "大家都说 XX 好，但其实..." |
| T08 信号转行动 | 多信号 → 判断窗口 → 执行步骤 | "现在该做什么，具体三步" |

---

## LLM 调用

| 环节 | 模型 | 调用次数/篇 | 用途 |
|------|------|------------|------|
| 泳道价值评估 | Haiku | 8 次/topic（可选） | 评估泳道写作价值 |
| 痛点提取 | Haiku | 1 次 | 提取读者痛点 |
| 文章生成 | Sonnet | 1 次 | 写文章 |
| 修复循环 | Sonnet | 0-5 次（按需） | 修复门禁违规 |
| 图表类型 | Haiku | N 次（可选） | 选图表类型 |

互动量抓取（fxtwitter）和数据补充（GitHub/网页）不消耗 token。

---

## 项目目录

```
growth-engine-pipeline/
├── pipeline/                     # 所有代码
│   ├── ingest/                   # L0: 信号采集
│   ├── engine/                   # L1: 主题引擎
│   ├── writer/                   # L2: 文章生成
│   ├── image/                    # L3: 配图
│   ├── publish/                  # L4: 分发发布
│   └── shared/                   # 共享工具
├── configs/                      # 所有配置
│   ├── frameworks/               # 8 个写作框架
│   ├── lanes/                    # 泳道配置
│   ├── writer/                   # 写作配置
│   ├── image/                    # 配图风格
│   └── account_influence.json    # 账号影响力等级
├── runtime/                      # 运行时数据
│   ├── accounts/                 # 账号 + 发布队列
│   ├── distribution/             # 分发计划
│   ├── library/                  # 文章成品库
│   └── runs/                     # Pipeline 产物
├── docs/                         # 文档
├── strategy/                     # 增长策略
├── run_pipeline.sh               # 一键执行
└── cron.example.sh               # 定时任务示例
```

---

## 使用方式

```bash
# 带审核（推荐）
./run_pipeline.sh --source-dirs "path/to/source_items"

# 跳过审核 + dry-run
./run_pipeline.sh --source-dirs "path/to/sources" --skip-review --dry-run

# 含 L0 抓取
./run_pipeline.sh --source-dirs "" --run-ingest

# 指定账号
./run_pipeline.sh --source-dirs "path/to/sources" --account xiaodao-ai-lab
```

---

## 环境要求

| 依赖 | 用途 | 必须 |
|------|------|------|
| Python 3.11+ | 所有脚本 | 是 |
| ANTHROPIC_API_KEY | Haiku + Sonnet | 是（需充值 API credits） |
| KIE_API_KEY | 配图 | 是 |
| bun | baoyu-image-gen | 是 |
| 比特浏览器 | X 发布 | 发布时需要 |
