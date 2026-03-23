# Framework Match podcast-practical_ai-c28e7eb8060b

- Routing Mode: llm_router_plus_reviewer
- Source Ref: /home/lyric/growth-engine-pipeline/content/runs/20260318_000000__podcast_ingest__default/03_source_items/podcast/items/podcast-practical_ai-c28e7eb8060b/source_item.json
- Prefilter Candidates: 03_opinion_decode
- Final Decision: 03_opinion_decode / conversation_distillation
- Final Confidence: high
- Human Review: False

## Router
- Model: codex-default
- Top Choice: 03_opinion_decode / conversation_distillation
- Rationale: This is a guest-led podcast interview with explicit participant structure and a clear人物弧线: Steve Klabnik moves from AI criticism to hands-on use, and the episode extracts his worldview and industry implications. That matches对话蒸馏 better than signal decoding because the payoff is the conversation itself, not a narrated external briefing.

## Reviewer
- Model: codex-default
- Agrees With Router: True
- Concerns: None
