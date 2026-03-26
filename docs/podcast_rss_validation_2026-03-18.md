# Podcast RSS 校准结果

- **日期**: 2026-03-18
- **状态**: Draft
- **关联产品**: 通用（YoloX 优先）

---

## 结论

这 9 个 podcast 的 RSS 我都做了实际 HTTP 请求校验。

- 技术上：`9/9` 都返回了可解析 XML
- 业务上：`8/9` 可直接进入日常 discovery
- 例外：
  - `The Gradient Podcast` 公开目录里有一个旧 Anchor feed，但那个 feed 只剩 `1` 条 `2021-12-05` 的旧内容，不应接入
  - 当前应使用的是 Substack-hosted 的 `The Gradient: Perspectives on AI` feed

## 推荐接入名单

| Podcast | 结果 | 最新一期时间 | 说明 |
|---------|------|-------------|------|
| Lex Fridman Podcast | 可用 | 2026-03-11 | 正常 RSS |
| TWIML AI Podcast | 可用 | 2026-03-10 | 正常 RSS |
| Practical AI | 可用 | 2026-03-17 | 正常 RSS |
| Latent Space | 可用 | 2026-03-17 | 正常 RSS |
| The Gradient: Perspectives on AI | 可用 | 2026-01-22 | 用 Substack 新 feed，不用旧 Anchor feed |
| The AI Daily Brief | 可用 | 2026-03-17 | 正常 RSS |
| The Cognitive Revolution | 可用 | 2026-03-16 | 正常 RSS |
| Hard Fork | 可用 | 2026-03-13 | 正常 RSS |
| Acquired | 可用 | 2026-03-02 | 正常 RSS |

## 采集层建议

这些 feed 当前都只适合做：

- `podcast_episode_metadata` discovery
- 生成 `episode card`
- 进入 transcript enrichment 队列

这些 feed 当前都不应该直接做：

- article 生成
- framework 套写

原因很简单：

- RSS 拿到的是标题、摘要、发布时间、链接
- 真正能进入下游改写的是 transcript 或足够长的 show notes

## 落盘文件

- 机器可读 registry:
  - [podcast_discovery_registry.json](/home/lyric/growth-engine-pipeline/content/source_acquisition/podcast_discovery_registry.json)
- 本轮校准说明:
  - [podcast_rss_validation_2026-03-18.md](/home/lyric/growth-engine-pipeline/content/source_acquisition/podcast_rss_validation_2026-03-18.md)
