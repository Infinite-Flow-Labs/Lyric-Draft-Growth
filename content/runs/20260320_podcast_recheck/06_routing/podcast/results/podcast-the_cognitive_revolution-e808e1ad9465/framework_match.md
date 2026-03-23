# Framework Match podcast-the_cognitive_revolution-e808e1ad9465

- Routing Mode: llm_router_plus_reviewer
- Source Ref: /home/lyric/growth-engine-pipeline/content/runs/20260320_podcast_recheck/03_source_items/podcast/items/podcast-the_cognitive_revolution-e808e1ad9465/source_item.json
- Prefilter Candidates: 03_opinion_decode, 05_ab_benchmark, 06_checklist_template
- Final Decision: 03_opinion_decode / signal_decode
- Final Confidence: high
- Human Review: False

## Router
- Model: bootstrap-from-prior-run
- Top Choice: 03_opinion_decode / signal_decode
- Rationale: This episode is a narrated AI market-and-research interpretation piece, not a guest-led conversational arc. The payoff comes from sorting multiple frontier-model and safety signals into one coherent judgment, which fits signal_decode better than conversation_distillation.

## Reviewer
- Model: bootstrap-from-prior-run
- Agrees With Router: True
- Concerns: None
