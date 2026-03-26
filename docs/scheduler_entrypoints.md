# Scheduler Entrypoints

OpenClaw should call one stable family entrypoint instead of stitching low-level scripts together.

Current supported families:

- `podcast`
- `official_x`
- `article_x`

Entrypoint:

```bash
python3 content/pipeline/scheduler/run_family.py --family podcast
python3 content/pipeline/scheduler/run_family.py --family official_x
python3 content/pipeline/scheduler/run_family.py --family article_x
```

Useful flags:

- `--dry-run`: print the planned command chain and run paths without executing.
- `--run-id <value>`: force a specific run id.
- `--backend auto|codex_cli|openai_compatible`: choose the router/writer backend.
- `--router-model / --reviewer-model / --writer-model`: override model names without changing pipeline code.
- `--include-human-review-required`: also write drafts for matches marked as requiring human review.

Run outputs are written under:

```text
content/runs/<run_id>/
```

After a successful run, the scheduler automatically syncs final article drafts into the unified article library and refreshes the global index.

Final article assets remain consumable from:

```text
content/library/articles/
```

After library sync, the scheduler now also does image-side production:

- default behavior: build `article_image_brief.json` for each newly synced article
- optional behavior: if `--generate-images` is enabled, also submit cover/inline image generation jobs

Post-run results are also written under:

```text
content/runs/<run_id>/09_post_run/
```

Useful files:

- `library_sync_result.json`
- `image_pipeline_result.json`

Useful image flags:

```bash
--skip-image-briefs
--generate-images
--image-max-inline 4
--image-wait
--image-dry-run
--image-api-key-env KIE_API_KEY
```

If you only want run artifacts without library sync, add:

```bash
--skip-library-sync
```
