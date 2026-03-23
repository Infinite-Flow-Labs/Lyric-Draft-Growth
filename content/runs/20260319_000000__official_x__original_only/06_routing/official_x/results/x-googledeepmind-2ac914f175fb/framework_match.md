# Framework Match x-googledeepmind-2ac914f175fb

- Routing Mode: llm_router_plus_reviewer
- Source Ref: /home/lyric/growth-engine-pipeline/content/runs/20260319_000000__official_x__original_only/03_source_items/official_x/items/x-googledeepmind-2ac914f175fb/source_item.json
- Prefilter Candidates: 01_money_proof, 02_launch_application
- Final Decision: 02_launch_application / release_showcase
- Final Confidence: high
- Human Review: False

## Router
- Model: codex-default
- Top Choice: 02_launch_application / release_showcase
- Rationale: This is a launch-led announcement post with a clear entry link and adoption CTA. It focuses on why the challenge is worth joining, not on deep implementation steps or metric postmortem evidence.

## Reviewer
- Model: codex-default
- Agrees With Router: True
- Concerns: Prize money ($200k) is an incentive signal, not evidence of achieved results; this should not trigger money-proof routing.
