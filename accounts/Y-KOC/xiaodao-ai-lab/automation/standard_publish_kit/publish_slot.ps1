param(
[string]$Date = $(Get-Date -Format "yyyy-MM-dd"),
[string]$Slot = "slot_01",
[string]$Time = "",
[string]$Profile = "profile.env"
)

$cfgPath = Join-Path $PSScriptRoot $Profile
if (!(Test-Path $cfgPath)) { throw "profile not found: $cfgPath" }

Get-Content $cfgPath | ForEach-Object {
if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
$k,$v = $_ -split '=',2
Set-Variable -Name $k -Value $v -Scope Script
}

$root = "${ACCOUNT_ROOT_WIN}\automation"
$tool = "$root\publish_tool"
$dir = "$root\publish_ready\$Date\$Slot"
$log = "$root\win_jobs\publish.log"

if (!(Test-Path "$dir\post.txt") -or !(Test-Path "$dir\post.jpg")) {
"[skip] missing files in $dir" | Tee-Object -FilePath $log -Append
exit 0
}
if (!(Test-Path $PYTHON_EXE)) {
"[error] python not found: $PYTHON_EXE" | Tee-Object -FilePath $log -Append
exit 1
}

if ([string]::IsNullOrWhiteSpace($Time)) {
if ($Slot -eq "slot_01") { $Time = "$Date 08:30" }
elseif ($Slot -eq "slot_02") { $Time = "$Date 12:00" }
else { $Time = "$Date 19:30" }
}

"[start] Date=$Date Slot=$Slot Time=$Time" | Tee-Object -FilePath $log -Append
Set-Location $tool

# 固定 Node 路径（统一运行时）
$env:PATH = "C:\Program Files\nodejs;" + $env:PATH

& $PYTHON_EXE -m x_schedule_post.cli `
--dir $dir `
--time $Time `
--timezone $TIMEZONE `
--accounts-csv "$root\win_jobs\accounts_bitbrowser.csv" `
--account $BIT_ACCOUNT `
--mcp-command "C:\Program Files\nodejs\npx.cmd" 2>&1 | Tee-Object -FilePath $log -Append
