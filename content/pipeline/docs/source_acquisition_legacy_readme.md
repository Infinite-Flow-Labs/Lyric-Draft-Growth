# Source Acquisition

- **日期**: 2026-03-18
- **状态**: Draft
- **关联产品**: 通用（YoloX 优先）

---

## 目录说明

这一层只负责内容源采集，不负责 framework 路由，不负责 article 生成。

## Source Family 边界（固定）

- `official_x`
  - 含义：官方 AI 公司 X 账号的帖子（post/thread）
  - 当前抓取器：`discover_official_x_guest_rss.py`
  - 说明：`original_only` / `with_replies` / `with_all` 是同一家族的抓取变体，不是新家族。
- `article_whitelist`
  - 含义：白名单站点或账号的 article（官方 blog / newsletter / changelog 等）
  - 当前抓取器：`discover_official_web_feeds.py` + `discover_official_web_posts.py`
  - 说明：这里是 article 语义，不与 `official_x` 混用。

当前已落地：

- `podcast_discovery_registry.json`
  - 已校准的 podcast RSS 名单
- `official_web_seed_registry.json`
  - `article_whitelist` 的 discovery seed，不是硬白名单
- `official_web_fallback_registry.template.json`
  - 可选 fallback whitelist 模板，只在 autodiscovery 没找到 feed 时兜底
- `discover_official_web_feeds.py`
  - 先从官网 / blog / newsletter landing page 做 feed autodiscovery，再用 fallback registry 兜底
- `discover_official_web_posts.py`
  - 从已验证 feed 批量发现 `article_whitelist` 文章 metadata
- `official_x_account_profile.json`
  - `official_x` 家族账号清单（用于游客态 RSS 抓取）
- `x_whitelist_account_profile.json`
  - `article_whitelist` 的 X 账号白名单（用于游客态 RSS 抓取）
- `discover_official_x_guest_rss.py`
  - 使用 Nitter RSS 以游客态批量抓取官方 X 账号近 7x24h 内容（默认过滤 reply/retweet）
- `filter_x_rss_article_candidates.py`
  - 从 X RSS 结果中过滤 article-like 帖子（按 `/article/`、blog/newsletter 等模式匹配）
- `linked_source_enrichment.py`
  - 通用外链补全模块：从 source 文本提取外链并抓取可读正文（report/blog/docs/changelog）
- `build_source_items_official_x.py`
  - 将 `guest_rss_catalog.json` 适配为 framework 消费的 `source_item.json`，并补全帖子外链上下文
- `discover_podcast_episodes.py`
  - 从 registry 批量发现新 episode，输出 `episode_catalog.json`
- `attach_podcast_transcript.py`
  - 给某条 episode 挂 transcript 或 show notes，输出 `transcript_source.json`
- `batch_attach_podcast_transcripts.py`
  - 读取 jobs manifest 批量挂 transcript 或 show notes，输出每条独立的 `transcript_source.json`
- `podcast_transcript_jobs.template.json`
  - 批量挂载任务模板，复制后填写真实 `source_id` / `origin_url` / `transcript_file` / `transcript_url`
- `discover_podcast_transcript_sources.py`
  - 从 episode 页面自动发现 show notes / transcript / subtitle 线索，能直接补全的就输出 `transcript_source.json`
- `build_source_items.py`
  - 把 `transcript_source.json` 或 metadata-only episode 适配成 framework 侧消费的 `source_item.json`

## 1. 发现 Podcast Episode

```bash
python3 content/source_acquisition/discover_podcast_episodes.py \
  --registry content/source_acquisition/podcast_discovery_registry.json \
  --out-dir content/source_runs/2026-03-18/discovery/podcast \
  --window-hours 72 \
  --max-per-show 5
```

输出：

- `episode_catalog.json`
- `episode_catalog.md`

`episode_catalog.json` 中的每条 episode 都是：

- `source_type = podcast_episode_metadata`
- `eligibility = trigger_until_transcript`

也就是说，它只能做 discovery，不应该直接拿去做 article 改写。

## 2. 挂载 Transcript / Show Notes

先准备一个 transcript 文件，支持：

- `.txt`
- `.md`
- `.vtt`
- `.srt`
- `.json`

如果是 JSON，脚本会读取这些字段之一：

- `text`
- `transcript`
- `content`
- `body`

命令：

```bash
python3 content/source_acquisition/attach_podcast_transcript.py \
  --episode-catalog content/source_runs/2026-03-18/discovery/podcast/episode_catalog.json \
  --source-id podcast-lex_fridman_podcast-xxxxxxxxxxxx \
  --transcript-file /path/to/transcript.txt \
  --out-dir content/source_runs/2026-03-18/fulltext/podcasts/lex_fridman_episode
```

如果拿到的是网页形式的 show notes 或 transcript URL，也可以直接挂：

```bash
python3 content/source_acquisition/attach_podcast_transcript.py \
  --episode-catalog content/source_runs/2026-03-18/discovery/podcast/episode_catalog.json \
  --origin-url https://example.com/episode/123 \
  --transcript-url https://example.com/episode/123/transcript \
  --out-dir content/source_runs/2026-03-18/fulltext/podcasts/example_episode
```

输出：

- `transcript_source.json`
- `transcript_source.md`

## 2.1 批量挂载 Transcript / Show Notes

如果你已经有一批 episode 对应的 transcript 文件或 URL，可以用 jobs manifest 批量执行。

示例任务模板：

- [podcast_transcript_jobs.template.json](podcast_transcript_jobs.template.json)

复制后填写真实值即可。

```json
{
  "jobs": [
    {
      "source_id": "podcast-practical_ai-xxxxxxxxxxxx",
      "transcript_file": "/tmp/episode-1.vtt",
      "attachment_mode": "subtitle_export"
    },
    {
      "origin_url": "https://example.com/episode/123",
      "transcript_url": "https://example.com/episode/123/transcript",
      "attachment_mode": "show_notes"
    }
  ]
}
```

命令：

```bash
python3 content/source_acquisition/batch_attach_podcast_transcripts.py \
  --episode-catalog content/source_runs/2026-03-18/discovery/podcast/episode_catalog.json \
  --jobs-file /path/to/jobs.json \
  --out-root content/source_runs/2026-03-18/fulltext/podcasts/batch_run
```

输出：

- 每条 job 对应一个子目录
- 每条 job 都会生成 `transcript_source.json` 和 `transcript_source.md`
- 额外生成 `batch_transcript_manifest.json`
- 额外生成 `batch_transcript_manifest.md`

## 2.2 自动发现并补全 Transcript / Show Notes

这一步会直接读取 `episode_catalog.json`，先抓 episode 页面，再自动判断：

- 页面本身是否已经是可读的 show notes / transcript
- 页面里是否能找到 transcript / show notes / YouTube 链接
- 如果命中 YouTube 链接且本机有 `yt-dlp`，则尝试抓字幕

命令：

```bash
python3 content/source_acquisition/discover_podcast_transcript_sources.py \
  --episode-catalog content/source_runs/2026-03-18/discovery/podcast/episode_catalog.json \
  --out-root content/source_runs/2026-03-18/fulltext/podcasts/auto_discovered
```

输出：

- 每条可补全的 episode 会生成自己的 `transcript_source.json`
- 额外生成 `transcript_discovery_manifest.json`
- 额外生成 `transcript_discovery_manifest.md`

这一步仍然只做采集和归一化，不做 framework 匹配，也不做 article 生成。

挂载完成后，这条 source 会变成：

- `source_type = podcast_transcript`
- `eligibility = direct_draft_source`

也就是它才有资格进入后续“只转写 / 转述 / 改写”的链路。

## 2.3 自动发现 Official Blog / Newsletter Feeds

这条链路不是“只吃白名单 feed URL”。

执行顺序是：

- 先从 AI 公司官网 / blog / newsletter landing page 做 RSS / Atom / JSON Feed autodiscovery
- 再尝试常见 feed path
- 最后才使用可选 fallback registry

种子页配置：

- `content/source_acquisition/official_web_seed_registry.json`

命令：

```bash
python3 content/source_acquisition/discover_official_web_feeds.py \
  --seed-registry content/source_acquisition/official_web_seed_registry.json \
  --out-dir content/source_runs/2026-03-19/discovery/official_web/feeds
```

如果后面你有自己的白名单 feed，可作为兜底传入：

```bash
python3 content/source_acquisition/discover_official_web_feeds.py \
  --seed-registry content/source_acquisition/official_web_seed_registry.json \
  --fallback-registry /path/to/official_web_fallback_registry.json \
  --out-dir content/source_runs/2026-03-19/discovery/official_web/feeds
```

输出：

- `official_web_registry.json`
- `feed_discovery_manifest.json`
- `feed_discovery_manifest.md`

## 2.4 发现 Official Blog / Newsletter 文章 Metadata

拿到已验证 feed registry 后，再批量发现近一段时间的文章。

```bash
python3 content/source_acquisition/discover_official_web_posts.py \
  --registry content/source_runs/2026-03-19/discovery/official_web/feeds/official_web_registry.json \
  --out-dir content/source_runs/2026-03-19/discovery/official_web/posts \
  --window-hours 168 \
  --max-per-site 10
```

输出：

- `article_catalog.json`
- `article_catalog.md`

注意：

- 这里拿到的仍然是 article metadata
- 下一步还需要 fulltext fetch / clean-up，才能进入 `source_item`

## 2.5 以游客态抓 Official X 账号（Nitter RSS）

这条链路不依赖 X 登录态，适合在 Playwright DOM 不稳定时做发现层抓取。

```bash
python3 content/source_acquisition/discover_official_x_guest_rss.py \
  --account-profile content/source_acquisition/official_x_account_profile.json \
  --out-dir content/source_runs/2026-03-19/discovery/official_x/guest_rss_original_only \
  --window-hours 168 \
  --max-per-handle 20
```

输出：

- `guest_rss_catalog.json`
- `guest_rss_catalog.md`

默认行为：

- 只保留 `original` 帖子
- 自动过滤 `reply` 和 `retweet`

如需包含回复或转推，加上：

```bash
  --include-replies --include-retweets
```

## 3.6 将 Official X Guest RSS 适配成 `source_item`

这一步会把游客态抓到的 X 帖子 metadata 标准化为 `SOURCE_ITEM_SCHEMA.json`，并自动尝试补全帖子外链（官方 blog / docs / report / changelog）。

```bash
python3 content/source_acquisition/build_source_items_official_x.py \
  --guest-rss-catalog content/source_runs/2026-03-19/discovery/official_x/guest_rss_original_only/guest_rss_catalog.json \
  --account-profile content/source_acquisition/official_x_account_profile.json \
  --out-root content/source_runs/2026-03-19/normalized/source_items/official_x_guest \
  --max-links 2 \
  --link-timeout 20
```

输出：

- 每条 source 一份 `source_item.json` + `source_item.md`
- 汇总 `source_item_manifest.json`

外链补全默认开启；如需关闭：

```bash
  --disable-link-enrichment
```

> 约定：其他内容家族接入时，如果 source 含外链/引用报告，也应复用 `linked_source_enrichment.py` 做同样的补全，而不是只用原贴短文本。

## 3. 推荐目录布局

```text
content/source_runs/
  2026-03-18/
    discovery/
      podcast/
        episode_catalog.json
        episode_catalog.md
    fulltext/
      podcasts/
        some_episode/
          transcript_source.json
          transcript_source.md
    normalized/
      source_items/
        podcast/
          some_source_id/
            source_item.json
            source_item.md
          source_item_manifest.json
```

## 3.1 生成 Source Item

在 framework 侧 schema 已就位后，把 podcast transcript 适配成 `source_item.json`：

```bash
python3 content/source_acquisition/build_source_items.py \
  --episode-catalog content/source_runs/2026-03-18/discovery/podcast/episode_catalog.json \
  --transcript-root content/source_runs/2026-03-18/fulltext/podcasts/auto_discovered \
  --out-root content/source_runs/2026-03-18/normalized/source_items/podcast
```

如果还想把没有 transcript 的 RSS metadata 也导成候选 `source_item`，加上：

```bash
  --include-metadata-only
```

输出：

- 每条 source 一个目录
- 每条 source 生成 `source_item.json`
- 每条 source 生成 `source_item.md`
- 汇总生成 `source_item_manifest.json`

当前实现已经直接按 framework 侧的 `SOURCE_ITEM_SCHEMA.json` 做校验。

## 3.2 生成 Prefilter 候选集

`prefilter` 只负责缩小候选 framework，不做最终 routing decision。

```bash
python3 content/source_acquisition/prefilter_framework_candidates.py \
  --source-item-root content/source_runs/2026-03-18/normalized/source_items/podcast \
  --out-root content/source_runs/2026-03-18/prefilter/podcast
```

输出：

- 每条 source 一个目录
- 每条 source 生成 `prefilter_result.json`
- 每条 source 生成 `prefilter_result.md`
- 汇总生成 `prefilter_manifest.json`

当前规则包含两类约束：

- 通用 heuristics：根据 `source_kind`、`task_hints`、标题/摘要关键词、正文弱信号做粗筛
- podcast bias control：`podcast_transcript` 不能只靠正文孤立词命中候选，避免 transcript 噪声把 router 带偏

这一层的边界是：

- 可以做 rule-based narrowing
- 不可以做最终 framework 决策
- 最终路由仍然必须交给 `router agent + reviewer agent`

## 3.3 组装 Rewrite Context

这一步严格按 framework 侧 contract 做 deterministic assembly，不允许再让 LLM 自由“总结 framework”。

```bash
python3 content/source_acquisition/build_rewrite_contexts.py \
  --framework-match-root content/source_runs/2026-03-18/routing/framework_matches/podcast \
  --out-root content/source_runs/2026-03-18/rewrite_contexts/podcast
```

输出：

- 每条 source 一个目录
- 每条 source 生成 `rewrite_context.json`
- 每条 source 生成 `rewrite_context.md`
- 汇总生成 `rewrite_context_manifest.json`

当前实现会直接按 framework 侧的 `REWRITE_CONTEXT_SCHEMA.json` 做校验。

## 3.4 受控生成 Article Draft

这一步读取：

- `source_item.json`
- `framework_match.json`
- `rewrite_context.json`

如果你想先挡掉明显不适合长文的 source，可以先跑一层很薄的 source gate。

```bash
python3 content/source_acquisition/evaluate_longform_gate.py \
  --source-item-root content/source_runs/2026-03-18/normalized/source_items/podcast \
  --out-root content/source_runs/2026-03-19/source_gate/podcast
```

输出：

- 每条 source 一个目录
- 每条 source 生成 `source_gate.json`
- 每条 source 生成 `source_gate.md`
- 汇总生成 `source_gate_manifest.json`

然后把 gate 直接接到 writer：

```bash
python3 content/source_acquisition/write_framework_articles.py \
  --rewrite-context-root content/source_runs/2026-03-18/rewrite_contexts/podcast \
  --source-gate-root content/source_runs/2026-03-19/source_gate/podcast \
  --out-root content/source_runs/2026-03-19/article_drafts/podcast_calibrated \
  --backend codex_cli \
  --output-language zh-CN
```

writer 只允许在 framework 已完成路由后生成，并且必须：

- 以 raw source 为 primary fact base
- 使用 deterministic 组装出来的 `rewrite_context.json`
- 不把 framework 再次压缩成自由发挥的 brief

命令：

```bash
python3 content/source_acquisition/write_framework_articles.py \
  --rewrite-context-root content/source_runs/2026-03-18/rewrite_contexts/podcast \
  --out-root content/source_runs/2026-03-18/article_drafts/podcast \
  --backend codex_cli \
  --output-language zh-CN
```

输出：

- 每条 source 一个目录
- 每条 source 生成 `article_draft.json`
- 每条 source 生成 `article_draft.md`
- 汇总生成 `article_draft_manifest.json`

当前实现还额外用本地的：

- `ARTICLE_DRAFT_SCHEMA.json`

校验 writer 输出，避免只返回一个标题或一段过短摘要。

## 4. 当前边界

这套脚本当前不做：

- 无上下文的全网 transcript 自动抓取
- framework 最终匹配

当前只先跑通：

- `RSS -> episode catalog`
- `manual transcript / subtitle / show notes -> transcript source`
- `batch jobs -> multiple transcript sources`
- `episode page auto-discovery -> transcript source`
- `transcript_source.json -> source_item.json`
- `source_item.json -> prefilter candidates`
- `framework_match.json -> rewrite_context.json`
- `rewrite_context.json + raw source -> article_draft.json`
