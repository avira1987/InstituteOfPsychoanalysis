# بیلد فرانت و بالا آوردن استک — از ریشهٔ ریپو اجرا کنید.
# مثال: .\scripts\docker-up.ps1

$ErrorActionPreference = "Stop"
# scripts/docker-up.ps1 -> project root = parent of scripts/
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

Write-Host "==> Building admin-ui (dist/)..." -ForegroundColor Cyan
Push-Location admin-ui
if (Test-Path package-lock.json) { npm ci } else { npm install }
npm run build
Pop-Location

Write-Host "==> docker compose up --build -d (db, redis, api)" -ForegroundColor Cyan
docker compose up --build -d db redis api

Write-Host ""
Write-Host 'Done. اگر خطای pull از Docker Hub دیدید، VPN یا اینترنت پایدار لازم است.' -ForegroundColor Yellow
Write-Host '  API + UI:  http://localhost:3000' -ForegroundColor Green
Write-Host '  Admin UI (dev serve): http://localhost:5173' -ForegroundColor Green
Write-Host '  Docs:      http://localhost:3000/docs' -ForegroundColor Green
