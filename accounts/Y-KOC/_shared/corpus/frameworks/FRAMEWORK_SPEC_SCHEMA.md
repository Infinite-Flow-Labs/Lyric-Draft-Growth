# FRAMEWORK_SPEC Schema

## Purpose

`FRAMEWORK_SPEC.json` is the full-fidelity machine execution spec for one framework.

It is **not**:

- a short summary
- a writer brief
- a replacement for the research `.md` files

It **is**:

- a structured projection of `FRAMEWORK.md`
- a structured projection of `STYLE_PROFILES.md`
- a structured projection of `SAMPLE_DECOMPOSITIONS.md`
- the machine-readable execution layer that routing and rewrite systems can safely consume

## Non-Lossy Rule

This schema exists to preserve framework quality, not to compress it away.

Three hard rules:

1. The research `.md` files remain the human source of truth.
2. `FRAMEWORK_SPEC.json` must preserve all execution-relevant detail from those `.md` files.
3. No field should be reduced to a vague label if the original framework contains a concrete rule, style move, or boundary.

If a future implementation tries to "simplify" a framework into a few keywords, that implementation is wrong.

## Layering

The framework system now has three layers:

### 1. Research Layer

Human-readable, detailed, revisable.

Files:

- `FRAMEWORK.md`
- `STYLE_PROFILES.md`
- `SAMPLE_DECOMPOSITIONS.md`

Use:

- human review
- framework boundary decisions
- style reasoning
- sample-based refinement

### 2. Spec Layer

Machine-readable, full-fidelity, structured.

File:

- `FRAMEWORK_SPEC.json`

Use:

- routing
- submode selection
- rewrite control
- deterministic context assembly

### 3. Runtime Layer

Source-specific execution payloads assembled from the spec layer.

Examples:

- `framework_match.json`
- `rewrite_context.json`

Use:

- per-source routing result
- per-source rewrite execution context

Important:

The runtime layer must be a deterministic selection from the spec layer.
It must not re-summarize or freehand compress the framework.

## What The Spec Must Preserve

Every framework spec must preserve these categories.

### Metadata

- framework identity
- confidence
- review status
- links to the human source files

### Intent

- definition
- core value
- core tasks

### Routing

- when the framework should be used
- when it should not be used
- strong signals
- weak signals
- disqualifiers
- source fit and source unfit conditions

### Structure

- hidden skeleton
- visible template bans
- allowed surface moves
- forbidden surface moves
- parameter axes
- submodes

### Style

- global style principles
- anti-AI rules
- submode-specific tone and rhythm
- opening moves
- surface forms
- language moves
- keep / avoid guidance

### Samples

- sample references
- sample-to-submode mapping
- reusable parts
- non-reusable parts
- style cues

### Execution Controls

- must keep
- must avoid
- rewrite failure modes
- quality checks
- human review triggers

## Why The Spec Is Separate From The Research Files

Because machines are bad at safely reading long, mixed natural-language documents.

Without a structured spec:

- routing logic becomes guessy
- style rules get lost
- anti-patterns get ignored
- low-confidence frameworks get treated like mature ones

The point of the spec is not to "make the framework shorter".
The point is to make framework execution precise.

## Field Design Principles

When filling a framework spec:

1. Prefer concrete strings over abstract labels.
2. Preserve submode boundaries explicitly.
3. Keep style controls as text-rich fields when needed.
4. Keep sample references attached to the framework.
5. Keep `confidence` mandatory.
6. Keep anti-AI rules mandatory.
7. Keep routing disqualifiers mandatory.

## Mapping Rule

The mapping from research docs to spec should follow this logic:

- `FRAMEWORK.md` -> metadata, intent, routing, structure, execution controls
- `STYLE_PROFILES.md` -> style
- `SAMPLE_DECOMPOSITIONS.md` -> samples

This is not a lossy summary.
It is a structured remapping.

## Validation Rule

A framework is not spec-complete unless:

- all required fields are present
- all submodes are mapped
- all style profiles are mapped
- all current sample references are mapped
- `confidence` is set
- quality controls are present

## Current Scope

This schema is the first machine-execution layer for the eight active frameworks:

- `01_money_proof`
- `02_launch_application`
- `03_opinion_decode`
- `04_failure_reversal`
- `05_ab_benchmark`
- `06_checklist_template`
- `07_contrarian_take`
- `08_signal_to_action`
