# Framework Match x-googledeepmind-2ac914f175fb

- Routing Mode: llm_router_plus_reviewer
- Source Ref: /home/lyric/growth-engine-pipeline/content/runs/20260319_official_x_recheck_v3/03_source_items/official_x/items/x-googledeepmind-2ac914f175fb/source_item.json
- Prefilter Candidates: 01_money_proof, 02_launch_application
- Final Decision: 02_launch_application / release_showcase
- Final Confidence: medium
- Human Review: False

## Router
- Model: codex-default
- Top Choice: 02_launch_application / release_showcase
- Rationale: The source is a launch-style X post pointing readers to a newly announced public challenge and linked framework entrypoint. It is not a quantified results post with a proof chain, so `01_money_proof` does not fit despite the prize amount. Within launch content, the reader payoff is mainly: why this is worth checking, what it is, and where to join, which matches a resource/showcase release better than a detailed adoption or feature explainer.

## Reviewer
- Model: codex-default
- Agrees With Router: True
- Concerns: The source is thin and somewhat news-like, so confidence should not be interpreted as strong content richness., `01_money_proof` is a prefilter false positive driven by prize-money signals rather than outcome evidence.
