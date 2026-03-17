param(
  [string]$Date = $(Get-Date -Format "yyyy-MM-dd"),
  [string]$Profile = "profile.env"
)

$cfgPath = Join-Path $PSScriptRoot $Profile
if (!(Test-Path $cfgPath)) { throw "profile not found: $cfgPath" }

Get-Content $cfgPath | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
  $k,$v = $_ -split '=',2
  Set-Variable -Name $k -Value $v -Scope Script
}

$remote = "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_ACCOUNT_ROOT}/automation/publish_ready/$Date/*"
$local  = "${ACCOUNT_ROOT_WIN}\\automation\\publish_ready\\$Date\\"
New-Item -ItemType Directory -Force -Path $local | Out-Null
scp -P $REMOTE_PORT -r $remote $local
Write-Host "[ok] synced $Date -> $local"
