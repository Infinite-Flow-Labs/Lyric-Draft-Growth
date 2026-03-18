# Pipeline Contract

## Purpose

This file defines how the framework worktree hands off to the pipeline worktree without losing the research quality already built into the framework docs and specs.

The core rule is:

- `FRAMEWORK.md` / `STYLE_PROFILES.md` / `SAMPLE_DECOMPOSITIONS.md` remain the human source of truth.
- `FRAMEWORK_SPEC.json` is the full-fidelity machine execution spec.
- runtime payloads may **select** from the full spec, but may not freely summarize it.

## Non-negotiables

1. `source -> framework` alignment must involve LLM routing.
2. rule-based prefiltering may narrow candidates, but may not make the final routing decision.
3. `rewrite_context.json` must be assembled deterministically from `FRAMEWORK_SPEC.json` after routing is finalized.
4. `rewrite_context.json` is **not** a brief and **not** a lossy summary.
5. writer must use raw source as the primary fact base.
6. low-confidence frameworks such as `05_ab_benchmark` and `08_signal_to_action` should default to reviewer support and often human review.

## Runtime Objects

### 1. `source_item.json`

Defined by:

- `SOURCE_ITEM_SCHEMA.json`

Purpose:

- normalize fetched source material before routing
- preserve raw source fidelity
- expose coarse signals for prefiltering without deciding the framework

What it must contain:

- raw source text
- source metadata
- normalized author / URL fields
- optional participants for interview / podcast sources
- optional source asset provenance when multiple transcript / show notes / subtitle sources are discovered
- primary text source selection and assembly notes when text is merged or chosen from multiple candidates
- extracted factual anchors
- light task hints only

### 2. `framework_match.json`

Defined by:

- `FRAMEWORK_MATCH_SCHEMA.json`

Purpose:

- record the result of `rules prefilter -> router agent -> reviewer agent -> final route`

Important:

- final route must come from LLM judgment, not pure rules
- reviewer is not optional in principle; it is especially important for ambiguous or low-confidence frameworks

What it must contain:

- prefilter candidate frameworks
- router top choice and alternatives
- reviewer agreement / override / concerns
- final framework + submode decision
- final confidence
- matched sample ids
- human review requirement

### 3. `rewrite_context.json`

Defined by:

- `REWRITE_CONTEXT_SCHEMA.json`

Purpose:

- hand the writer exactly the relevant slice of the selected framework
- preserve depth without re-summarizing the framework

Important:

- this file is assembled by code, not authored by an LLM summary step
- it should carry exact selected packets from the full framework spec:
  - selected submode spec
  - selected style profile
  - selected sample refs
  - execution controls

It must not:

- rewrite the framework in looser words
- collapse style into a few vague adjectives
- flatten hidden structure into visible template headings

## Recommended Flow

1. fetch and normalize source
2. produce `source_item.json`
3. run rule-based prefilter to narrow framework candidates
4. run router agent on source + candidate framework specs
5. run reviewer agent on router result
6. produce `framework_match.json`
7. deterministically assemble `rewrite_context.json` from selected `FRAMEWORK_SPEC.json`
8. run writer on `source_item.json + rewrite_context.json`
9. optionally run critic / reviewer on output before publish

## Quality Notes

- framework routing quality is upstream of writing quality. If routing drifts, downstream writing will drift even with a strong writer.
- deterministic context assembly is necessary because letting an LLM "brief the framework" will silently drop constraints.
- writer should learn both:
  - what to write
  - how to write

That means every rewrite should preserve:

- source facts
- framework logic
- submode structure
- sample-derived voice and rhythm
- anti-AI constraints

## Current Risk Flags

- `05_ab_benchmark`: only 2 samples, low confidence
- `08_signal_to_action`: only 2 samples and same author, low confidence

These two are enabled, but should not be treated as equal to the more mature frameworks during router confidence handling.
