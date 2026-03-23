# Framework Match x-cohere-88b540bdac01

- Routing Mode: llm_router_plus_reviewer
- Source Ref: /home/lyric/growth-engine-pipeline/content/runs/20260319_official_x_recheck/03_source_items/official_x/items/x-cohere-88b540bdac01/source_item.json
- Prefilter Candidates: 06_checklist_template
- Final Decision: 06_checklist_template / curated_list
- Final Confidence: low
- Human Review: True

## Router
- Model: codex-default
- Top Choice: 06_checklist_template / curated_list
- Rationale: Only candidate framework available. The source points readers to multiple GTC sessions and a booth, so `curated_list` is the closest submode, but fit is weak because the post is promotional and lacks real筛选、demo、repo或执行路径。

## Reviewer
- Model: codex-default
- Agrees With Router: True
- Concerns: The source is primarily event promotion, not a true tutorial/checklist/listicle, so overall framework fit is weak., `curated_list` is only a nearest-match fallback here; the post does not show real selection, demos, repos, or actionable comparison value., Prefilter likely over-weighted `tutorial` hints from linked context rather than the actual X post reader payoff.
