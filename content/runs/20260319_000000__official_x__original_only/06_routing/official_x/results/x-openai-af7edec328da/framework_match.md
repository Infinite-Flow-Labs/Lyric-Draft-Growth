# Framework Match x-openai-af7edec328da

- Routing Mode: llm_router_plus_reviewer
- Source Ref: /home/lyric/growth-engine-pipeline/content/runs/20260319_000000__official_x__original_only/03_source_items/official_x/items/x-openai-af7edec328da/source_item.json
- Prefilter Candidates: 01_money_proof, 06_checklist_template
- Final Decision: 06_checklist_template / guided_onboarding
- Final Confidence: low
- Human Review: True

## Router
- Model: codex-default
- Top Choice: 06_checklist_template / guided_onboarding
- Rationale: Among the provided frameworks, this source is closest to an action-oriented onboarding entry point: a challenge CTA plus a link likely containing participation steps. It does not show the proof chain, timeline, or postmortem structure required by money-proof frameworks.

## Reviewer
- Model: codex-default
- Agrees With Router: True
- Concerns: In-thread evidence is very thin and does not explicitly contain step-by-step onboarding content; checklist fit is inferred from the linked page., The post can also be read as a launch/challenge teaser, so submode confidence is inherently limited., Dollar signals look like prize incentives rather than audited outcomes, so money_proof remains a weak fit.
