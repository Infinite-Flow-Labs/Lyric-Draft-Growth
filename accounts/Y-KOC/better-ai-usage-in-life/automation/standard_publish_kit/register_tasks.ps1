param(
  [string]$TaskPrefix = "XPost-Auto",
  [string]$Profile = "profile.env"
)

$base = $PSScriptRoot
$ps = "powershell.exe"
$argSync = "-ExecutionPolicy Bypass -File `"$base\\sync_publish_ready.ps1`" -Profile `"$Profile`""
$argP1   = "-ExecutionPolicy Bypass -File `"$base\\publish_slot.ps1`" -Profile `"$Profile`" -Slot slot_01"
$argP2   = "-ExecutionPolicy Bypass -File `"$base\\publish_slot.ps1`" -Profile `"$Profile`" -Slot slot_02"
$argP3   = "-ExecutionPolicy Bypass -File `"$base\\publish_slot.ps1`" -Profile `"$Profile`" -Slot slot_03"

$actSync = New-ScheduledTaskAction -Execute $ps -Argument $argSync
$actP1   = New-ScheduledTaskAction -Execute $ps -Argument $argP1
$actP2   = New-ScheduledTaskAction -Execute $ps -Argument $argP2
$actP3   = New-ScheduledTaskAction -Execute $ps -Argument $argP3

$trSync = New-ScheduledTaskTrigger -Daily -At 08:10
$trP1   = New-ScheduledTaskTrigger -Daily -At 08:30
$trP2   = New-ScheduledTaskTrigger -Daily -At 12:00
$trP3   = New-ScheduledTaskTrigger -Daily -At 19:30
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Unregister-ScheduledTask -TaskName "$TaskPrefix-Sync" -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "$TaskPrefix-Post-0830" -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "$TaskPrefix-Post-1200" -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "$TaskPrefix-Post-1930" -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask -TaskName "$TaskPrefix-Sync" -Action $actSync -Trigger $trSync -Settings $settings -Description "Sync publish_ready"
Register-ScheduledTask -TaskName "$TaskPrefix-Post-0830" -Action $actP1 -Trigger $trP1 -Settings $settings -Description "Publish slot_01"
Register-ScheduledTask -TaskName "$TaskPrefix-Post-1200" -Action $actP2 -Trigger $trP2 -Settings $settings -Description "Publish slot_02"
Register-ScheduledTask -TaskName "$TaskPrefix-Post-1930" -Action $actP3 -Trigger $trP3 -Settings $settings -Description "Publish slot_03"

Get-ScheduledTask | Where-Object {$_.TaskName -like "$TaskPrefix*"} | Select-Object TaskName,State
