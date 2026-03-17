# local_publish (run on your BitBrowser machine)

## 1) Prepare
1. Copy this folder to your local machine.
2. Ensure local machine has:
   - python3
   - rsync + ssh
   - BitBrowser running and logged in
3. Put your x-post project at: `$LOCAL_WORK_ROOT/automation` (or modify config)
4. Copy `config.env.example` -> `config.env`, then fill values.

## 2) Test sync only
```bash
bash sync_publish_ready.sh 2026-03-12
```

## 3) Dry-run publish
```bash
bash run_publish_today.sh 2026-03-12 1
```

## 4) Real publish
```bash
bash run_publish_today.sh 2026-03-12 0
```

## 5) Cron (example)
```cron
# every day 08:05 sync + publish schedule for today (real run)
5 8 * * * /bin/bash /path/to/local_publish/run_publish_today.sh $(date +\%F) 0 >> /path/to/local_publish/publish.log 2>&1
```
