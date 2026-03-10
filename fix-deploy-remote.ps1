$HostIP = "80.191.11.129"
$HostPort = 2022
$HostUser = "root"
$HostPass = "parsbpms.com"
$HostKey = "SHA256:F459aXR14g147aSBxWlTypGEKisuxzYnrYl4kcDyPdA"

# SMS env از .env
$smsEnv = ""
if (Test-Path (Join-Path $PSScriptRoot ".env")) {
    Get-Content (Join-Path $PSScriptRoot ".env") -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_ -match '^\s*SMS_PROVIDER=(.+)$') { $smsEnv += " -e SMS_PROVIDER=$($matches[1].Trim())" }
        if ($_ -match '^\s*SMS_API_KEY=(.+)$') { $smsEnv += " -e SMS_API_KEY=$($matches[1].Trim())" }
        if ($_ -match '^\s*SMS_LINE_NUMBER=(.+)$') { $smsEnv += " -e SMS_LINE_NUMBER=$($matches[1].Trim())" }
    }
}

$plinkPath = $null
foreach ($p in @("$PSScriptRoot\plink.exe", "C:\Program Files\PuTTY\plink.exe", "C:\Program Files (x86)\PuTTY\plink.exe", "plink")) {
    if ($p -match "\\" -and (Test-Path $p)) { $plinkPath = $p; break }
    if ($p -notmatch "\\") { $x = Get-Command $p -ErrorAction SilentlyContinue; if ($x) { $plinkPath = $x.Source; break } }
}
if (-not $plinkPath) { Write-Host "plink not found"; exit 1 }

Write-Host "=== Building and running anistito-api on server ===" -ForegroundColor Cyan
$cmd = "cd /opt/anistito && echo '--- Docker build ---' && docker build -t anistito-api . 2>&1 && echo '--- Docker run ---' && docker rm -f anistito-api 2>/dev/null || true && docker run -d --name anistito-api --network anistito-net -p 3000:3000 -e DATABASE_URL=postgresql+asyncpg://anistito:anistito@anistito-db:5432/anistito -e DATABASE_URL_SYNC=postgresql://anistito:anistito@anistito-db:5432/anistito -e REDIS_URL=redis://anistito-redis:6379/0 -e DEBUG=false -e SECRET_KEY=anistito-prod-secret$smsEnv anistito-api:latest sh -c 'python -m alembic upgrade head 2>/dev/null || true && python -m uvicorn app.main:app --host 0.0.0.0 --port 3000' 2>&1 && sleep 8 && echo '--- Container status ---' && docker ps -a --filter name=anistito-api && echo '--- Last logs ---' && docker logs anistito-api --tail 30 2>&1 && echo '--- Health ---' && curl -s http://127.0.0.1:3000/health 2>&1 || echo 'curl failed'"
$out = & $plinkPath -P $HostPort -pw $HostPass -hostkey $HostKey -batch "${HostUser}@${HostIP}" $cmd 2>&1
Write-Host $out
