$ErrorActionPreference = "Stop"

$KEY="$env:USERPROFILE\.ssh\xpost_sync"
$HOST="root@43.156.25.67"
$REMOTE_BASE="/root/.openclaw/agent-workspaces/growth-assistant"
$DATE=(Get-Date).AddDays(1).ToString("yyyy-MM-dd")
$ACCOUNTS=@("xiaodao-ai-lab","better-ai-usage-in-life","lyric-workflow-diary")
$LOCAL_BASE="E:\X-Tweet-Publish\Y-KOC"

# 1) 云端：生成明天内容 + 配图 + 产出 publish_ready
$remoteCmd = @"
set -e
DATE=$DATE
BASE=$REMOTE_BASE
set -a; source \$BASE/.kie.env; set +a
for A in xiaodao-ai-lab better-ai-usage-in-life lyric-workflow-diary; do
python3 \$BASE/accounts/Y-KOC/\$A/automation/generate_plan.py --account-root \$BASE/accounts/Y-KOC/\$A --date \$DATE
python3 \$BASE/accounts/Y-KOC/\$A/automation/daily_pipeline.py --config \$BASE/accounts/Y-KOC/\$A/automation/config.json --date \$DATE --model gpt-5.3-codex --max-rewrites 2
python3 \$BASE/accounts/Y-KOC/\$A/automation/pre_publish_validate.py --account-root \$BASE/accounts/Y-KOC/\$A --date \$DATE
python3 \$BASE/accounts/Y-KOC/\$A/automation/publish_from_calendar.py --account-root \$BASE/accounts/Y-KOC/\$A --date \$DATE >/tmp/\${A}_pub.log
for i in 01 02 03; do
python3 \$BASE/skills/apimart-image-gen/scripts/kie_image.py \
--article \$BASE/accounts/Y-KOC/\$A/calendar/\$DATE/contents/post_\${i}.md \
--out \$BASE/accounts/Y-KOC/\$A/calendar/\$DATE/contents/assets/post_\${i}.image.json \
--aspect-ratio 16:9 --resolution 2K --output-format jpg \
--download-dir \$BASE/accounts/Y-KOC/\$A/calendar/\$DATE/contents/assets \
--filename-prefix post_\${i}_1 --wait 300
cp \$BASE/accounts/Y-KOC/\$A/calendar/\$DATE/contents/assets/post_\${i}_1_1.jpg \
\$BASE/accounts/Y-KOC/\$A/calendar/\$DATE/contents/assets/post_\${i}_1.jpg
done
python3 \$BASE/accounts/Y-KOC/\$A/automation/publish_from_calendar.py --account-root \$BASE/accounts/Y-KOC/\$A --date \$DATE >/tmp/\${A}_pub2.log
done
"@
ssh -i $KEY $HOST "bash -lc '$remoteCmd'"

# 2) 同步到本地（只拉 publish_ready）
foreach($a in $ACCOUNTS){
$localPR = "$LOCAL_BASE\$a\automation\publish_ready\$DATE"
New-Item -ItemType Directory -Force -Path $localPR | Out-Null
scp -i $KEY -r "${HOST}:${REMOTE_BASE}/accounts/Y-KOC/$a/automation/publish_ready/$DATE/slot_*" "$localPR\"
}
# 3) 本地执行排程（把明天 3 个 slot 全部送进 schedule）
foreach($a in $ACCOUNTS){
$winJobs = "$LOCAL_BASE\$a\automation\win_jobs\publish_slot.ps1"
powershell -ExecutionPolicy Bypass -File $winJobs -Date $DATE -Slot slot_01 -Profile "profile.env"
powershell -ExecutionPolicy Bypass -File $winJobs -Date $DATE -Slot slot_02 -Profile "profile.env"
powershell -ExecutionPolicy Bypass -File $winJobs -Date $DATE -Slot slot_03 -Profile "profile.env"
}

Write-Host "DONE: tomorrow($DATE) prepared + synced + scheduled."