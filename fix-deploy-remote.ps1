$HostIP = "80.191.11.129"
$HostPort = 2022
$HostUser = "root"
$HostPass = "parsbpms.com"
$HostKey = "SHA256:F459aXR14g147aSBxWlTypGEKisuxzYnrYl4kcDyPdA"

# Alocom/SMS از .env لوکال → --env-file روی سرور
$integFrag = Join-Path $env:TEMP "anistito-integration.env"
$envFileArg = ""
& python (Join-Path $PSScriptRoot "scripts\integration_env_sync.py") --fragment-only $integFrag
if (($LASTEXITCODE -eq 0) -and (Test-Path $integFrag) -and ((Get-Item $integFrag).Length -gt 0)) {
    $envFileArg = " --env-file /tmp/anistito-integration.env"
    Write-Host "Integration env (Alocom/SMS) will be passed to container" -ForegroundColor Gray
}

$plinkPath = $null
$pscpPath = $null
foreach ($p in @("$PSScriptRoot\plink.exe", "C:\Program Files\PuTTY\plink.exe", "C:\Program Files (x86)\PuTTY\plink.exe", "plink")) {
    if ($p -match "\\" -and (Test-Path $p)) { $plinkPath = $p; break }
    if ($p -notmatch "\\") { $x = Get-Command $p -ErrorAction SilentlyContinue; if ($x) { $plinkPath = $x.Source; break } }
}
foreach ($p in @("$PSScriptRoot\pscp.exe", "C:\Program Files\PuTTY\pscp.exe", "C:\Program Files (x86)\PuTTY\pscp.exe", "pscp")) {
    if ($p -match "\\" -and (Test-Path $p)) { $pscpPath = $p; break }
    if ($p -notmatch "\\") { $x = Get-Command $p -ErrorAction SilentlyContinue; if ($x) { $pscpPath = $x.Source; break } }
}
if (-not $plinkPath) { Write-Host "plink not found"; exit 1 }

if ($envFileArg -and $pscpPath) {
    & $pscpPath -P $HostPort -pw $HostPass -hostkey $HostKey $integFrag "${HostUser}@${HostIP}:/tmp/anistito-integration.env"
    if ($LASTEXITCODE -ne 0) { Write-Host "Integration env upload failed"; exit 1 }
}

Write-Host "=== Building and running anistito-api on server ===" -ForegroundColor Cyan
$cmd = "cd /opt/anistito && echo '--- Docker build ---' && docker build -t anistito-api . 2>&1 && echo '--- Docker run ---' && docker rm -f anistito-api 2>/dev/null || true && docker run -d --name anistito-api --network anistito-net -p 3000:3000$envFileArg -e DATABASE_URL=postgresql+asyncpg://anistito:anistito@anistito-db:5432/anistito -e DATABASE_URL_SYNC=postgresql://anistito:anistito@anistito-db:5432/anistito -e REDIS_URL=redis://anistito-redis:6379/0 -e DEBUG=false -e SECRET_KEY=anistito-prod-secret anistito-api:latest sh -c 'python -m alembic upgrade head 2>/dev/null || true && python -m uvicorn app.main:app --host 0.0.0.0 --port 3000' 2>&1 && sleep 8 && echo '--- Container status ---' && docker ps -a --filter name=anistito-api && echo '--- Last logs ---' && docker logs anistito-api --tail 30 2>&1 && echo '--- Health ---' && curl -s http://127.0.0.1:3000/health 2>&1 || echo 'curl failed'"
$out = & $plinkPath -P $HostPort -pw $HostPass -hostkey $HostKey -batch "${HostUser}@${HostIP}" $cmd 2>&1
Write-Host $out
Remove-Item $integFrag -Force -ErrorAction SilentlyContinue
