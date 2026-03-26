# Project Directory

```
growth-engine-pipeline/
├── pipeline/                     # All pipeline code
│   ├── ingest/                   # L0: source acquisition
│   │   ├── x/                    # X/Twitter ingestion
│   │   ├── podcast/              # Podcast ingestion
│   │   ├── normalize.py          # Source item normalization
│   │   └── build_source_items*.py
│   ├── engine/                   # L1: topic engine
│   │   ├── topic_engine.py       # Clustering + routing + ranking
│   │   ├── backend.py            # LLM backends (Anthropic/OpenAI/Codex)
│   │   └── build_rewrite_contexts.py
│   ├── writer/                   # L2: article generation
│   │   ├── writer.py             # Main writer (pain point + generation + repair)
│   │   └── formatter.py          # Article blocks + validation + sanitize
│   ├── image/                    # L3: image generation
│   │   ├── brief_builder.py      # Build image brief from article
│   │   ├── generator.py          # Call baoyu/kie image APIs
│   │   └── run_image_pipeline.py # Orchestrate brief → generate
│   ├── publish/                  # L4: distribution + publish
│   │   ├── assemble_queues.py    # Assign articles to accounts
│   │   ├── publisher.py          # Orchestrate image → queue → publish
│   │   └── x_post/              # X Articles publisher (bitbrowser)
│   └── shared/                   # Shared utilities
│
├── configs/                      # All configuration
│   ├── frameworks/               # 8 framework specs (01-08)
│   ├── lanes/                    # Lane maps + topic engine policy
│   ├── writer/                   # Humanizer, signal boost, schema
│   ├── image/                    # Style profiles, brief template, style bridge
│   └── publish/                  # Publish contract
│
├── runtime/                      # All runtime data
│   ├── accounts/                 # Account profiles + publish queues
│   ├── distribution/             # Distribution plans + manifests
│   ├── library/                  # Published article archive
│   └── runs/                     # Pipeline run outputs
│
├── docs/                         # Documentation
│   ├── lane_contracts/           # Per-lane requirements
│   └── *.md                      # Architecture, contracts, specs
│
└── strategy/                     # Growth strategy docs
```

## Pipeline Flow

```
L0  pipeline/ingest/          → source_item.json
L1  pipeline/engine/          → topic_card + lane_assignment + writer_packet
L2  pipeline/writer/          → article_draft.json + article_draft.md
L3  pipeline/image/           → cover.png + inline_*.png
L4  pipeline/publish/         → publish via bitbrowser to X Articles
```
