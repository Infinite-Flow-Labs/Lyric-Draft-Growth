# Project Directory Guide

## Quick Reference

```
growth-engine-pipeline/
├── lane_v2/                    # Core pipeline code (L1 + L2)
│   ├── assemble/               # L1: topic engine (clustering + routing)
│   ├── route/                  # LLM backends (Anthropic/OpenAI/Codex)
│   ├── write/                  # L2: writer + article_formatter
│   ├── normalize/              # L0: source item normalization
│   ├── configs/                # Writer configs (HUMANIZER, SIGNAL_BOOST, SCHEMA)
│   ├── docs/                   # Lane contracts
│   └── runs/                   # Pipeline run outputs (gitignored in production)
│
├── content/pipeline/           # L0 + L3 + L4 code
│   ├── ingest/                 # L0: source acquisition (podcast, x_whitelist)
│   ├── normalize/              # L0: legacy source normalization
│   ├── shared/                 # Shared utilities (web_feed_utils, enrichment)
│   ├── write/                  # article_formatter wrapper (→ lane_v2)
│   ├── publish/                # L3: image + L4: distribution + publish
│   ├── configs/                # Image configs (STYLE_PROFILES, BRIEF template)
│   └── _legacy/                # Deprecated code (do not use)
│
├── framework/                  # 8 framework specs (01-08)
│
├── configs/                    # [NEW] Unified config mirror
│   ├── frameworks/             # Mirror of framework/
│   ├── lanes/                  # Mirror of lane_v2/configs/lane_pilot/
│   ├── writer/                 # Mirror of lane_v2/configs/
│   ├── image/                  # Mirror of content/pipeline/configs/
│   └── publish/                # Publish contracts
│
├── docs/                       # [NEW] Unified documentation
│   ├── lanes/                  # Lane requirements + contracts
│   ├── article_contract.md
│   └── article_image_style_spec.md
│
├── tools/                      # External tools
│   └── x-schedule-post/        # X Articles publisher (modified, in-repo)
│
├── accounts_runtime/           # Account profiles + publish queues
├── distribution_runtime/       # Distribution plans + manifests
├── content/library/            # Published article archive
│
└── strategy/                   # Growth strategy docs
```

## Pipeline Flow (which code runs where)

```
L0  ingest     → content/pipeline/ingest/ + lane_v2/normalize/
L1  engine     → lane_v2/assemble/run_t01_topic_engine.py
L2  writer     → lane_v2/write/write_lane_articles.py
L3  image      → content/pipeline/publish/run_article_image_pipeline.py
L4  publish    → content/pipeline/publish/run_image_distribute_publish.py
                  → tools/x-schedule-post/x_schedule_post/cli.py
```

## Config Locations (authoritative source)

| Config | Authoritative Path | Mirror |
|--------|-------------------|--------|
| Framework specs | `framework/0N_*/FRAMEWORK_SPEC.json` | `configs/frameworks/` |
| Lane map | `lane_v2/configs/lane_pilot/lane_framework_map.v1.json` | `configs/lanes/` |
| Writer configs | `lane_v2/configs/*.json` | `configs/writer/` |
| Image configs | `content/pipeline/configs/*.json` | `configs/image/` |

**Important**: The authoritative source is the original location. `configs/` is a mirror for discoverability. If you edit a config, edit it at the authoritative path.
