# Unified Content Workflow (Rules Engine + First-hand Source Engine)

## Why merge
- Old chain = writing rules / structure / quality stability
- New chain = first-hand source moat (podcast/interview/transcript)
- Unified chain = unique source + stable publish quality

## Pipeline
1. `generate_plan.py` + `daily_pipeline.py` -> short posts
2. Kie image generation -> assets
3. `build_hot_signals.py` + `generate_a_article_plan.py` + `article_pipeline_a.py` -> A article
4. Optional interview branch:
   - `transcript_pipeline.py --input <transcript.txt>`
   - `interview_rewrite.py`
   - `quote_extractor.py`
5. `publish_from_calendar.py` packages all available content types.

## Unified calendar layout
- `calendar/YYYY-MM-DD/sources/` (raw/clean/selected/topics)
- `calendar/YYYY-MM-DD/publish/posts/`
- `calendar/YYYY-MM-DD/publish/article/`
- `calendar/YYYY-MM-DD/publish/interview/` (optional)

## Content types packaged
- `slot_01..03` (`content_type=post`)
- `article/` (`content_type=article`)
- `interview/` (`content_type=interview`, optional)

## Run
```bash
# standard (post + article)
./run_daily_pipeline.sh 2026-03-17

# with interview transcript source
INTERVIEW_SOURCE=/path/to/transcript.txt ./run_daily_pipeline.sh 2026-03-17
```

## Key artifacts
- `calendar/YYYY-MM-DD/article/article_x_ready.txt`
- `calendar/YYYY-MM-DD/interview/article_interview_x_ready.txt`
- `automation/publish_ready/YYYY-MM-DD/`
