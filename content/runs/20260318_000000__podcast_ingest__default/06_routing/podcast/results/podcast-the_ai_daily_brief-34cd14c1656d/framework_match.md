# Framework Match podcast-the_ai_daily_brief-34cd14c1656d

- Routing Mode: llm_router_plus_reviewer
- Source Ref: /home/lyric/growth-engine-pipeline/content/runs/20260318_000000__podcast_ingest__default/03_source_items/podcast/items/podcast-the_ai_daily_brief-34cd14c1656d/source_item.json
- Prefilter Candidates: 03_opinion_decode, 01_money_proof
- Final Decision: 03_opinion_decode / signal_decode
- Final Confidence: high
- Human Review: False

## Router
- Model: codex-default
- Top Choice: 03_opinion_decode / signal_decode
- Rationale: This is a narrated industry briefing that decodes AI agent adoption, enterprise readiness, and competitive moves. It is not dialogue-led, and the reader payoff comes from interpreting the signals and why they matter, which matches signal_decode better than conversation_distillation.

## Reviewer
- Model: codex-default
- Agrees With Router: True
- Concerns: None
