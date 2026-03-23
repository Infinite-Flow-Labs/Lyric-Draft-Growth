# 内容源采集策略

- **日期**: 2026-03-18
- **状态**: Draft
- **关联产品**: 通用（YoloX 优先）

---

## 目标

第二部分当前只做 **source acquisition**，不做 framework 对接，不做 article 生成。

要先回答三个问题：

1. 我们要抓什么类型的内容源
2. 每类内容源通过什么渠道发现
3. 每类内容源应该怎么获取，拿到什么粒度的数据

核心原则只有一条：

> 既然下游要求“只转写 / 转述 / 改写，不做原创生文”，那采集层就必须优先抓 **证据足够长、信息足够密、上下文足够完整** 的 source。

所以采集层要把 source 分成两类：

- `Direct Draft Source`
  - 可以直接进入后续 article 改写
- `Trigger Source`
  - 只能触发选题或补充信号，不能单独拿来生成 article

## Source 类型分层

### P0: 直接可改写的长源

这是 v1 必须先做的。

| 类型 | 内容单元 | 渠道 | 获取方式 | 下游资格 |
|------|---------|------|---------|---------|
| Benchmark X Article | 单篇 X Article / 长文 | 对标账号 Timeline | 账号级抓取 + article 抽取 | Direct Draft Source |
| Benchmark X Thread | 同作者 thread / 长推 | 对标账号 Timeline | `x-tweet-fetcher` 抓取并合并 thread | Direct Draft Source（仅限信息密度够高） |
| Podcast Transcript | 单期播客逐字稿 | Podcast RSS + YouTube/官网 transcript | RSS 发现 episode，再抓 transcript | Direct Draft Source |
| Official Blog / Changelog | 单篇官方博客 / release note | 官方博客 / docs / changelog | RSS / 页面轮询 / GitHub Releases | Direct Draft Source |
| Newsletter / Blog Post | 单篇 newsletter / blog | Substack / Beehiiv / Medium / 独立站 | RSS / 邮件转存 / 页面抓取 | Direct Draft Source |

### P1: 高价值触发源

这是 v1.5 可以接入的。

| 类型 | 内容单元 | 渠道 | 获取方式 | 下游资格 |
|------|---------|------|---------|---------|
| Fast X Post | 单条短推 | 对标账号 / AI 大 V | `x-tweet-fetcher` | Trigger Source |
| GitHub Release / README | 单次 release / README 更新 | GitHub | RSS / Release 页面 / Repo 页面 | Trigger Source，必要时补长源 |
| Product Hunt / HN / Reddit | 单条帖子 | 平台榜单 / 社区 | RSS / HTML 抓取 | Trigger Source |

### P2: 暂不优先

这些源不是没价值，而是现阶段容易把采集层做重。

| 类型 | 原因 |
|------|------|
| 纯音频无 transcript 的播客 | 没有逐字稿就不适合“只改写不创作” |
| 社群聊天记录 / Discord 片段 | 噪声高，结构差，清洗成本高 |
| 论文 PDF 原文 | 信息密度高但转写成本高，容易变成“AI 总结”而不是稳定 article 改写 |

## 推荐的 Source 家族

### 1. 对标账号长内容

这是最接近你当前目标的 source。

#### 1.1 Benchmark X Article

- 定义：
  - 对标账号发布的 X Article 或带完整 article 结构的长内容
- 为什么优先：
  - 天然已经是 article 形态，最适合后续做“套框架改写”
- 发现渠道：
  - benchmark account timeline
  - benchmark account RSS
- 获取方式：
  - 先按账号维度发现候选 status
  - 再对候选 status 做 article 识别与正文抽取
- 推荐实现：
  - 候选发现：Nitter RSS / timeline 抽样
  - 稳定抓取：Playwright 登录态抓取
  - 正文补全：article DOM 抽取
- 输出粒度：
  - 标题
  - preview
  - 正文全文
  - 作者
  - 发布时间
  - 原始 URL
  - engagement metadata

#### 1.2 Benchmark X Thread

- 定义：
  - 对标账号在 X 上的长 thread，尤其是教程、复盘、观点拆解类
- 为什么优先：
  - 这类内容虽然不是 article，但结构清晰，容易转为 article
- 发现渠道：
  - benchmark account timeline
- 获取方式：
  - 直接复用 `x-tweet-fetcher`
- 推荐实现：
  - 以账号为单位，抓最近 `24h` 或 `72h`
  - 合并同作者 thread
  - 对 thread 做长度、段数、主题词过滤
- 进入下游的门槛：
  - `segment_count >= 3`
  - 有明确主题，不是碎碎念
  - 能提取出 3 个以上有效 claim / step / lesson

### 2. 播客 / 访谈 / YouTube 长谈话

这类 source 非常重要，但不要把“播客发现”和“播客可改写”混为一谈。

#### 2.1 Podcast Episode Metadata

- 定义：
  - 通过 RSS 拿到的 episode 标题、简介、发布时间、链接
- 渠道：
  - Podcast RSS
  - YouTube Channel uploads feed
- 用途：
  - 只负责发现新一期，不直接进 article 改写
- 下游资格：
  - `Trigger Source`

#### 2.2 Podcast / Video Transcript

- 定义：
  - 逐字稿、字幕、show notes 长摘要
- 渠道：
  - 官方 transcript 页面
  - YouTube 字幕
  - show notes / newsletter recap
  - 手工导入 transcript
- 用途：
  - 这是播客类真正能进入 article 改写的 source
- 推荐实现：
  - 第一步只做 RSS 发现和 transcript 挂载接口
  - transcript 拿不到时，只保留 episode card，不做生成

#### 2.3 为什么播客要拆两层

因为：

- RSS 只有标题和 summary，不够支撑“只改写不创作”
- 真正可用的是 transcript
- 所以播客采集层要分成：
  - `discover_episode`
  - `enrich_transcript`

### 3. 官方发布源

这是“发布应用型”和“热点整理型”的关键 source。

#### 3.1 Official Blog / Docs / Changelog

- 典型来源：
  - 模型厂商博客
  - 产品 changelog
  - docs 更新页
  - GitHub releases
- 为什么优先：
  - 信息准确
  - 上线快
  - 适合“发布了什么 / 我怎么用”
- 获取方式：
  - RSS 优先
  - 无 RSS 时轮询 changelog / release page
  - GitHub release 可单独做轻量轮询
- 下游资格：
  - Direct Draft Source

### 4. Newsletter / Blog

这是“观点拆解型”和“信号整理型”的高质量 source。

- 典型来源：
  - Substack
  - Beehiiv
  - Medium
  - 独立博客
- 为什么值得接：
  - 结构通常完整
  - 已经是 article 形态
- 获取方式：
  - RSS 优先
  - 邮件转存为 markdown / html
  - 页面抓取作为兜底
- 下游资格：
  - Direct Draft Source

## 采集渠道定义

采集渠道不要按平台名定义，要按“发现机制”定义。

### 1. Account Timeline

- 适合：
  - 对标 X 账号
- 特征：
  - 按账号拉近 `24h / 72h / 168h`
- 推荐工具：
  - `x-tweet-fetcher`
- 优点：
  - 直接贴合 benchmark accounts
- 风险：
  - 登录态依赖
  - DOM 变化

### 2. RSS Feed

- 适合：
  - Podcast
  - Blog
  - Newsletter
  - GitHub releases
- 特征：
  - 稳定、轻量、适合 cron
- 优点：
  - 成本低
  - 易去重
  - 易增量抓取
- 风险：
  - 很多源只有摘要，没有全文

### 3. Page Polling

- 适合：
  - 官方 changelog
  - docs 更新页
  - 没有 RSS 的博客
- 特征：
  - 定时抓 HTML，做 diff
- 优点：
  - 适用面广
- 风险：
  - 容易脆
  - 要做内容变化判断

### 4. Manual Drop-In

- 适合：
  - transcript
  - 私有 newsletter
  - 手工保存的网页 / markdown / txt
- 特征：
  - 把文件丢进指定目录，系统只负责 ingest
- 为什么必须有：
  - transcript 获取常常不稳定
  - 很多高价值源根本不适合全自动抓

## 获取方式定义

每种 source 都应该拆成两个动作，而不是一步到位：

1. `discover`
2. `fetch_fulltext`

### Discover

只做这些事情：

- 发现是否有新内容
- 记录标题、摘要、时间、URL、作者
- 生成 source card

### Fetch Fulltext

只对值得进入后续链路的 source 执行：

- 拉正文 / transcript / thread text
- 补 metadata
- 存原始文本

这样做的原因是：

- 大部分 source 不值得抓全文
- 先发现再补全文，系统更稳
- 可以把成本留给高价值 source

## v1 应该先做什么

只做四条采集链路，够了。

### 链路 A: Benchmark X Thread

- 渠道：
  - account timeline
- 获取：
  - `x-tweet-fetcher`
- 产物：
  - `raw_posts.json`
  - `normalized_posts.json`
  - `benchmark-aggregate.json`
- 角色：
  - Direct Draft Source
  - Trigger Source

### 链路 B: Benchmark X Article

- 渠道：
  - benchmark accounts timeline / RSS
- 获取：
  - 候选发现 + article 正文抽取
- 产物：
  - `article_source.json`
  - `article_source.md`
- 角色：
  - Direct Draft Source

### 链路 C: Podcast RSS + Transcript

- 渠道：
  - RSS
  - transcript page / subtitles / manual drop-in
- 获取：
  - 先抓 episode metadata
  - 再补 transcript
- 产物：
  - `episode_catalog.json`
  - `transcript_source.json`
- 角色：
  - metadata 是 Trigger Source
  - transcript 是 Direct Draft Source

### 链路 D: Official Blog / Changelog / Newsletter

- 渠道：
  - RSS / page polling
- 获取：
  - 新文章发现
  - 全文抽取
- 产物：
  - `web_source.json`
  - `web_source.md`
- 角色：
  - Direct Draft Source

## 不同 source 的下游约束

为了避免后面又回到“凭空补全”，采集层要提前做资格判断。

| Source 类型 | 允许直接进改写 | 说明 |
|------------|---------------|------|
| X Article 正文 | 是 | 最优先 |
| 高质量 X Thread | 是 | 需要长度和结构门槛 |
| Podcast transcript | 是 | 必须有 transcript |
| Official blog / newsletter 全文 | 是 | 信息完整 |
| Podcast RSS summary | 否 | 只能做发现 |
| 单条短推 | 否 | 只能做信号 |
| Product Hunt / HN / Reddit 单帖 | 否 | 只能做触发 |

## 存储建议

建议统一按日期跑批：

```text
content/source_runs/
  2026-03-18/
    discovery/
      x_benchmark/
      podcast/
      official_web/
    fulltext/
      x_articles/
      x_threads/
      podcasts/
      newsletters/
    manifests/
      source_catalog.json
      source_catalog.md
```

每个 source record 至少要有这些字段：

- `source_id`
- `source_family`
- `source_type`
- `discovery_channel`
- `author`
- `origin_url`
- `published_at`
- `title`
- `summary`
- `fulltext_path`
- `language`
- `eligibility`
- `fetch_status`

## 推荐的执行顺序

### 第一步

先把 source 家族定成下面 4 类：

- benchmark x thread
- benchmark x article
- podcast transcript
- official blog / newsletter

### 第二步

每类都只做：

- 发现
- 去重
- 存 source card

### 第三步

只对这两类补全文：

- benchmark x article
- podcast transcript

### 第四步

再把：

- official blog / newsletter
- 高质量 x thread

接进来

## 结论

当前第二部分不要泛化成“全网抓取”，而要聚焦成四种可控 source：

1. 对标账号的 X Article
2. 对标账号的高质量 Thread
3. AI 播客 / 访谈的 transcript
4. 官方博客 / newsletter / changelog

其中：

- `RSS` 是发现层主力
- `x-tweet-fetcher` 是 benchmark X 账号主力
- `transcript` 必须单独作为一层，不要和 podcast discovery 混在一起
- 短推 / 榜单 / 社区帖只能做 trigger，不能直接当 article source

这套边界定清楚之后，后面再接 framework 才不会重新退化成“AI 自己补内容”。
