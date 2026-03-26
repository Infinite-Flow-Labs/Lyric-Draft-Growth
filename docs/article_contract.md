# Article Contract

This is the global article contract shared by all currently supported families:

- `podcast`
- `official_x`
- `article_x`

The contract is family-agnostic. Family only affects source shape and framework routing, not final article structure.

## Goals

- Keep article quality improvements global instead of family-specific.
- Separate writing quality from publishing formatting.
- Let writer produce structured article blocks instead of only one large markdown blob.
- Let the publisher consume richer structure for X Articles formatting later.

## Current Fields

Core content fields:

- `title`
- `dek`
- `body_markdown`

New structured publishing fields:

- `article_blocks[]`
- `publishing_hints{}`

## Supported Block Types

- `hero_heading`
- `section_heading`
- `paragraph`
- `bullet_list`
- `quote`
- `link_cta`
- `closing_slogan`

## Block Semantics

- `hero_heading`: large hook-like line near the top of the article.
- `section_heading`: strong mid-article reset to prevent reader drop-off.
- `paragraph`: normal narrative block.
- `bullet_list`: compact list of points or takeaways.
- `quote`: source attribution or highlighted cited block.
- `link_cta`: outbound action block with optional `url` and `label`.
- `closing_slogan`: reusable account-level ending line or signature block.

## Publishing Hints

`publishing_hints` is optional and may contain:

- `source_label`
- `source_url`
- `closing_slogan`
- `primary_link_url`
- `primary_link_label`

These hints are for the publishing layer. They should not be treated as writer-only ornament.

## Compatibility

- Old articles without `article_blocks` remain readable.
- The assembler will synthesize article text from `article_blocks` when available.
- The queue now also emits `article_publish_spec.json` so the article publisher can later format blocks directly inside X Articles.
