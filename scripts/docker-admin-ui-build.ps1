#Requires -Version 5.0
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repoRoot

Write-Host "Building admin-ui in Docker (output: admin-ui/dist)..." -ForegroundColor Cyan
docker compose --profile admin-ui-build run --rm admin-ui-build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Done." -ForegroundColor Green
