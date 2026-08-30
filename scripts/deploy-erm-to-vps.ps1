# Deploy ERM to VPS after GitHub push.
# Usage: powershell -File scripts/deploy-erm-to-vps.ps1

param(
  [string]$Remote = "sentinel-hk",
  [string]$Path = "/opt/enterprise-risk-assessment",
  [string]$Service = "erm-assessment.service"
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $here ".git"))) {
  $here = "D:\_Work\01_Projects\enterprise-risk-assessment"
}

Set-Location $here
git push -u origin HEAD
if ($LASTEXITCODE -ne 0) { throw "git push failed" }

$cmd = @"
set -e
cd $Path
if [ ! -d .git ]; then
  git init -b main
  git remote add origin https://github.com/bjin5700-ship-it/enterprise-risk-assessment.git 2>/dev/null || true
fi
git fetch origin
git checkout -B main origin/main
systemctl restart $Service
systemctl is-active $Service
"@
ssh $Remote $cmd
Write-Host "ERM deployed"
