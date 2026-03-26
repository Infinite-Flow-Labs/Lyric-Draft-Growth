# Distribution Runtime

This tree stores distribution planning and queue assembly artifacts.

It sits between:

- `content/library/articles/` as the content source pool
- `accounts_runtime/<account_id>/publish_queue/` as the account execution target

Layout:

```text
distribution_runtime/
  plans/
    YYYY-MM-DD/
      distribution_plan.json
  manifests/
    YYYY-MM-DD/
      distribution_manifest.json
  schemas/
    publish_job.schema.json
```

Rules:

- `plans/` records intended content-to-account assignments.
- `manifests/` records what queue files were actually assembled.
- `schemas/` stores runtime contract files used by the distribution layer.
