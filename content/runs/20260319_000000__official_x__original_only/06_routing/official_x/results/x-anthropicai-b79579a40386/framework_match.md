# Framework Match x-anthropicai-b79579a40386

- Routing Mode: llm_router_plus_reviewer
- Source Ref: /home/lyric/growth-engine-pipeline/content/runs/20260319_000000__official_x__original_only/03_source_items/official_x/items/x-anthropicai-b79579a40386/source_item.json
- Prefilter Candidates: 01_money_proof, 06_checklist_template
- Final Decision: 01_money_proof / metric_postmortem
- Final Confidence: medium
- Human Review: True

## Router
- Model: codex-default
- Top Choice: 01_money_proof / metric_postmortem
- Rationale: The source is driven by quantified outcome signals and study-scale execution context (sample size, timeframe, geography/language coverage), which aligns best with a metrics-focused postmortem lens rather than a tutorial or onboarding template.

## Reviewer
- Model: codex-default
- Agrees With Router: True
- Concerns: `01_money_proof/metric_postmortem` is the best available fit, but the item is a research-announcement thread rather than a classic business KPI postmortem., Process evidence is partially dependent on linked-page context; if routing is evaluated on the X post alone, it may resemble a result-only claim., Candidate set appears to lack a dedicated research-insight/reporting framework, creating residual classification ambiguity.
