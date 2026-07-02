param(
  [string]$FrontendRoot = "/public"
)

$ErrorActionPreference = "Stop"
$markerStart = "<!-- AgentMascot global loader start -->"
$markerEnd = "<!-- AgentMascot global loader end -->"
$indexPath = Join-Path $FrontendRoot "index.html"
if (!(Test-Path -LiteralPath $indexPath)) {
  throw "MoviePilot frontend index.html not found: $indexPath"
}

$content = Get-Content -LiteralPath $indexPath -Raw
$pattern = "(?s)\s*" + [regex]::Escape($markerStart) + ".*?" + [regex]::Escape($markerEnd) + "\s*"
if ($content -notmatch [regex]::Escape($markerStart)) {
  Write-Host "AgentMascot loader patch not found: $indexPath"
  exit 0
}

$backupPath = "$indexPath.agentmascot-unpatch.$(Get-Date -Format 'yyyyMMddHHmmss').bak"
Copy-Item -LiteralPath $indexPath -Destination $backupPath
$content = [regex]::Replace($content, $pattern, "`n")
Set-Content -LiteralPath $indexPath -Value $content -Encoding UTF8
Write-Host "AgentMascot loader patch removed: $indexPath"
Write-Host "Backup: $backupPath"
