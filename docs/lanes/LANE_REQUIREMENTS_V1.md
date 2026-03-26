# Lane Requirements V1

## Scope
This file defines the 8-lane contract used by `lane_v2/assemble/run_t01_topic_engine.py`.

## Lanes

### T01_release_decode
- Framework: `02_launch_application/release_showcase`
- Composition: `generation 0.8 / rewrite 0.2`
- Minimum sources: `primary>=2`, `supporting>=1`, `fact_anchors>=6`
- Hard requirements:
  - official primary source
  - release signal
  - actionability signal
- Preferences:
  - stepwise signal

### T02_signal_decode
- Framework: `03_opinion_decode/signal_decode`
- Composition: `generation 0.4 / rewrite 0.6`
- Minimum sources: `primary>=1`, `supporting>=2`, `fact_anchors>=8`
- Hard requirements:
  - external source

### T03_money_proof
- Framework: `01_money_proof/metric_postmortem`
- Composition: `generation 0.3 / rewrite 0.7`
- Minimum sources: `primary>=2`, `supporting>=1`, `fact_anchors>=8`
- Hard requirements:
  - hard numbers signal

### T04_failure_reversal
- Framework: `04_failure_reversal/system_pivot`
- Composition: `generation 0.5 / rewrite 0.5`
- Minimum sources: `primary>=2`, `supporting>=2`, `fact_anchors>=7`
- Hard requirements:
  - failure signal

### T05_benchmark
- Framework: `05_ab_benchmark/alternative_benchmark`
- Composition: `generation 0.4 / rewrite 0.6`
- Minimum sources: `primary>=3`, `supporting>=1`, `fact_anchors>=10`
- Hard requirements:
  - compare signal
  - hard numbers signal

### T06_capability_delivery
- Framework: `06_checklist_template/workflow_architecture`
- Composition: `generation 0.6 / rewrite 0.4`
- Minimum sources: `primary>=2`, `supporting>=2`, `fact_anchors>=8`
- Hard requirements:
  - actionability signal
- Preferences:
  - stepwise signal

### T07_contrarian_take
- Framework: `07_contrarian_take/category_reframe`
- Composition: `generation 0.7 / rewrite 0.3`
- Minimum sources: `primary>=2`, `supporting>=2`, `fact_anchors>=8`
- Preferences:
  - contrarian signal

### T08_signal_to_action
- Framework: `08_signal_to_action/market_window_playbook`
- Composition: `generation 0.75 / rewrite 0.25`
- Minimum sources: `primary>=2`, `supporting>=3`, `fact_anchors>=10`
- Hard requirements:
  - external source
  - actionability signal
- Preferences:
  - stepwise signal

