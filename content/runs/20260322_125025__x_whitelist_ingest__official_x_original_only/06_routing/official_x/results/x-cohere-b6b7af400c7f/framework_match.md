# Framework Match x-cohere-b6b7af400c7f

- Routing Mode: llm_router_plus_reviewer
- Source Ref: /home/lyric/growth-engine-pipeline/content/runs/20260322_125025__x_whitelist_ingest__official_x_original_only/03_source_items/official_x/items/x-cohere-b6b7af400c7f/source_item.json
- Prefilter Candidates: 03_opinion_decode
- Final Decision: 03_opinion_decode / signal_decode
- Final Confidence: medium
- Human Review: False

## Router
- Model: gpt-5.4
- Top Choice: 03_opinion_decode / signal_decode
- Rationale: The source is a company event post about public appearances, partner meetings, and enterprise AI themes at GTC. That fits an external-signal/item decode better than conversation-led distillation. There is a named public action and industry-event context, but little dialogue structure,人物弧线, or interview material to justify conversation_distillation.

## Reviewer
- Model: gpt-5.4
- Agrees With Router: True
- Concerns: The source is promotional and thin, so the framework fit is acceptable but not especially rich., `conversation_distillation` would be a poor fit because there is no explicit guest/dialogue evidence, quotes, or scene-level reconstruction.
