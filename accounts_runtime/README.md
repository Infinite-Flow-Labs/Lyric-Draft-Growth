# Accounts Runtime

This tree stores runtime publishing assets by account.

It is intentionally separate from:

- `framework/` for static framework assets and benchmark-account reference files
- `content/library/articles/` for generated content assets
- `content/runs/` for pipeline execution artifacts

Per-account layout:

```text
accounts_runtime/
  <account_id>/
    profile/
      account_profile.json
      publisher_config.json
    publish_queue/
      YYYY-MM-DD/
        01/
          post.txt
          post.jpg
          article_publish_spec.json
          publish_job.json
    published/
      YYYY-MM-DD/
        01/
          post.txt
          post.jpg
          article_publish_spec.json
          publish_job.json
          publish_result.json
    logs/
```

Rules:

- `profile/` stores static account-level config.
- `publish_queue/` stores pending publishing units.
- `published/` stores completed publishing units and publish results.
- `logs/` stores account-local operational logs only.
- Queue items should be directly consumable by the external `x-post` publisher.
- For article publishing, queue slots may also contain `article_publish_spec.json` for richer block-based formatting.

Templates live under:

- [accounts_runtime/_template](/home/lyric/growth-engine-pipeline/accounts_runtime/_template)
- [distribution_runtime/schemas](/home/lyric/growth-engine-pipeline/distribution_runtime/schemas)
