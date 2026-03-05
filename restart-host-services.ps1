# Restart all anistito services on host and verify

$HostIP = "80.191.11.129"
$HostPort = 2022
$HostUser = "root"
$HostPass = "parsbpms.com"
$HostKey = "SHA256:F459aXR14g147aSBxWlTypGEKisuxzYnrYl4kcDyPdA"

$plinkPath = $null
foreach ($p in @("$PSScriptRoot\plink.exe", "C:\Program Files\PuTTY\plink.exe", "C:\Program Files (x86)\PuTTY\plink.exe", "plink")) {
    if ($p -match "\\" -and (Test-Path $p)) { $plinkPath = $p; break }
    if ($p -notmatch "\\") { $x = Get-Command $p -ErrorAction SilentlyContinue; if ($x) { $plinkPath = $x.Source; break } }
}

if (-not $plinkPath) {
    Write-Host "plink not found. Install PuTTY." -ForegroundColor Red
    exit 1
}

Write-Host "=== Connecting to host ===" -ForegroundColor Cyan

$cmds = @"
echo '=== 1. Current containers ==='
docker ps -a --filter name=anistito --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

echo ''
echo '=== 2. Restarting anistito-api ==='
docker restart anistito-api 2>/dev/null || echo 'Container not found. Starting...'
docker start anistito-api 2>/dev/null || true

echo ''
echo '=== 3. Restarting anistito-db (PostgreSQL) ==='
docker restart anistito-db 2>/dev/null || echo 'anistito-db not found'

echo ''
echo '=== 4. Restarting anistito-redis ==='
docker restart anistito-redis 2>/dev/null || echo 'anistito-redis not found'

echo ''
echo '=== 5. Restarting Apache ==='
systemctl restart apache2 2>/dev/null || systemctl restart httpd 2>/dev/null || echo 'Apache restart skipped'

echo ''
echo '=== 6. Waiting 15s for services ==='
sleep 15

echo ''
echo '=== 7. Container status ==='
docker ps --filter name=anistito --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

echo ''
echo '=== 8. Health check (API) ==='
curl -s -w '\nHTTP:%{http_code}' http://127.0.0.1:8000/health 2>&1 || echo 'FAIL'

echo ''
echo '=== 9. API process count ==='
curl -s http://127.0.0.1:8000/debug/process-count 2>&1 || echo 'N/A'

echo ''
echo '=== 10. Website via proxy (curl) ==='
curl -s -o /dev/null -w 'HTTP:%{http_code}' http://127.0.0.1/anistito/ 2>/dev/null || curl -s -o /dev/null -w 'HTTP:%{http_code}' https://bpms.psychoanalysis.ir/anistito/ 2>/dev/null || echo 'N/A'
"@

$ErrorActionPreference = "Continue"
$out = & $plinkPath -P $HostPort -pw $HostPass -hostkey $HostKey -batch "${HostUser}@${HostIP}" $cmds 2>&1
$ErrorActionPreference = "Stop"

Write-Host $out
Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Green
Write-Host "URL: https://bpms.psychoanalysis.ir/anistito/" -ForegroundColor White
