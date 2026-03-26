# lane_v2 Workspace

This is an isolated lane workspace copied from the current pipeline.

## Scope
- Independent working area for lane/topic experiments.
- Files are copied, not moved, so other worktrees/windows are unaffected.

## Structure
- `assemble/`: topic engine (`run_t01_topic_engine.py`)
- `write/`: lane writer (`write_lane_articles.py`, `article_formatter.py`)
- `route/`: backend client and model call utilities (`route_framework_matches.py`)
- `normalize/`: X source normalization (`build_source_items_official_x.py`)
- `configs/`: lane policy and writer config packets
- `docs/`: lane contract docs
- `runs/`: lane_v2 run outputs

## Entrypoints
Topic engine:

```bash
python3 lane_v2/assemble/run_t01_topic_engine.py \
  --source-item-root <path_to_source_items_a> \
  --source-item-root <path_to_source_items_b> \
  --out-root lane_v2/runs/<run_id>/t01_topic_engine
```

Lane writer:

```bash
python3 lane_v2/write/write_lane_articles.py \
  --writer-packet-root lane_v2/runs/<run_id>/t01_topic_engine/06_writer_packets/writer_packet_manifest.json \
  --out-root lane_v2/runs/<run_id>/t01_lane_articles \
  --backend codex_cli \
  --writer-model gpt-5.4 \
  --output-language zh-CN
```

