# Framework Handoff Map

- **日期**: 2026-03-18
- **状态**: Draft
- **关联产品**: 通用（YoloX 优先）

---

## 目的

这份文档只做一件事: 把当前采集层产物整理成对 framework 侧可消费的输入映射。

它不是新协议，不定义新的 contract，不替代 framework 侧的 `SOURCE_ITEM_SCHEMA.json` / `REWRITE_CONTEXT_SCHEMA.json`。

## 当前采集层产物

### 1. `podcast_discovery_registry.json`

用途:
- 配置要监控哪些 podcast feed

它不直接给 framework:
- 不是 source item
- 不是 rewrite input

它只提供上游来源配置。

### 2. `episode_catalog.json`

用途:
- 从 RSS 自动发现 episode metadata

可视为 framework 侧的候选输入，但还不是最终输入。

适合映射到的稳定字段:
- `source_id`
- `source_type`
- `origin_url`
- `published_at`
- `title`
- `summary`
- `author`
- `show_label`
- `language`

需要保留的上下文字段:
- `show_id`
- `feed_url`
- `audio_url`
- `guid`
- `transcript_mode`
- `eligibility`
- `fetch_status`

### 3. `transcript_source.json`

用途:
- 把 episode 补成可改写的正文源

这是当前最接近 framework 侧 `source_item` 的产物。

适合映射到的稳定字段:
- `source_id`
- `source_type = podcast_transcript`
- `origin_url`
- `published_at`
- `title`
- `summary`
- `author`
- `show_label`
- `fulltext_path`
- `fulltext_url`
- `eligibility = direct_draft_source`
- `fetch_status = transcript_attached`

附加字段:
- `transcript.path`
- `transcript.source_url`
- `transcript.attachment_mode`
- `transcript.word_count`
- `transcript.line_count`
- `text`

### 4. `transcript_discovery_manifest.json`

用途:
- 汇总自动发现结果

它不直接进 framework，最多作为批处理审计。

可用于追踪:
- 哪些 episode 已直补成功
- 哪些只是 candidate
- 哪些未找到可用正文

## 最小输入映射

下面是当前采集层对 framework 侧最小可消费输入的建议映射。

| 采集层字段 | framework 侧建议语义 | 备注 |
|---|---|---|
| `source_id` | source 主键 | 稳定唯一 |
| `source_type` | source 类型 | 例如 `podcast_episode_metadata` / `podcast_transcript` |
| `origin_url` | 原始来源 URL | 必填优先 |
| `published_at` | 发布时间 | ISO 时间串 |
| `title` | 标题 | 原始标题 |
| `summary` | 摘要 / show notes 摘要 | 原文保留 |
| `author` | 来源作者 / show name | 不强行改成人名 |
| `show_label` | 播客节目名 | 播客场景下很重要 |
| `fulltext_path` | 本地正文路径或正文来源 | transcript 完整后才有 |
| `fulltext_url` | 正文 URL | 如果正文来自网页则保留 |
| `eligibility` | 是否可进 rewrite | `trigger_until_transcript` / `direct_draft_source` |
| `fetch_status` | 获取状态 | 例如 `discovered` / `transcript_attached` / `auto_discover` |

## 哪些字段是派生字段

这些字段适合保留，但不应该成为 framework 侧判定主依据:

- `word_count`
- `line_count`
- `candidate_urls`
- `score`
- `score_reasons`
- `evaluated_count`
- `attachment_mode`
- `discovery_mode`
- `discovery_evidence`

## 哪些字段不该下沉进 framework 主契约

这些字段对采集层有用，但不适合作为 framework 主输入依赖:

- `feed_url`
- `audio_url`
- `guid`
- `registry_ref`
- `window`
- `stats`
- batch manifest 内的运行信息

原因:
- 它们是采集过程的运行元数据
- framework 侧真正需要的是“内容本体 + 来源可追溯性”

## framework 对接时的判断顺序

建议 framework 侧按下面顺序消费:

1. 先看 `eligibility`
   - `trigger_until_transcript` 只做触发，不进入 rewrite
   - `direct_draft_source` 才可进入后续流程
2. 再看 `source_type`
   - 区分 metadata / transcript / 其他长源
3. 再看 `origin_url` 和 `published_at`
   - 作为 provenance 和时序判断
4. 最后看 `text` / `summary`
   - 以原始素材为事实基底

## 给 framework 侧的实现建议

如果 framework 侧需要一个统一输入，建议它消费的不是“摘要”，而是下面这一层:

- source 本体
- 原始正文
- provenance
- eligibility
- 基本运行元数据

不要让采集层去提前做 framework 级别的总结，否则后面会丢失可改写的细节。

## 当前结论

当前采集层已经能稳定产出两类输入:

- `episode_catalog.json`
  - 适合做候选池
- `transcript_source.json`
  - 适合做 framework 的直接输入候选

因此对 framework 侧最重要的对接点是:

`transcript_source.json -> SOURCE_ITEM_SCHEMA.json`

而不是:

`episode_catalog.json -> framework`
