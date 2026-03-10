# تشخیص مشکل Service Unavailable - اجرا از ویندوز
# اتصال به سرور و نمایش وضعیت

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
    Write-Host "plink not found. Install PuTTY or use manual SSH:" -ForegroundColor Red
    Write-Host "ssh -p 2022 root@80.191.11.129" -ForegroundColor Yellow
    exit 1
}

Write-Host "=== اتصال به سرور و تشخیص مشکل ===" -ForegroundColor Cyan

$cmds = @"
echo '=== 1. وضعیت کانتینر anistito-api ==='
docker ps -a --filter name=anistito-api --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

echo ''
echo '=== 2. لاگ آخر کانتینر ==='
docker logs anistito-api --tail 60 2>&1 || echo '(کانتینر وجود ندارد)'

echo ''
echo '=== 3. پورت 3000 ==='
ss -tlnp 2>/dev/null | grep 3000 || netstat -tlnp 2>/dev/null | grep 3000 || echo 'پورت 3000 باز نیست'

echo ''
echo '=== 4. تست health ==='
curl -s -w '\nHTTP_CODE:%{http_code}' http://127.0.0.1:3000/health 2>&1 || echo 'curl failed'

echo ''
echo '=== 5. ProxyPass در Apache ==='
grep -r 'anistito\|ProxyPass' /etc/apache2/sites-enabled/ 2>/dev/null | head -15 || grep -r 'anistito\|ProxyPass' /etc/httpd/conf.d/ 2>/dev/null | head -15
"@

$ErrorActionPreference = "Continue"
$out = & $plinkPath -P $HostPort -pw $HostPass -hostkey $HostKey -batch "${HostUser}@${HostIP}" $cmds 2>&1
$ErrorActionPreference = "Stop"

Write-Host $out
Write-Host ""
Write-Host "=== Troubleshooting ===" -ForegroundColor Cyan
Write-Host "If container Exited: check docker logs anistito-api (migration/import error)"
Write-Host "If port 3000 not listening: container not running, run deploy again"
Write-Host "If no ProxyPass: run scripts/fix_apache_anistito.sh on server"
Write-Host "To restart: cd /opt/anistito && docker start anistito-api"
Write-Host "To redeploy: .\deploy-to-host.ps1"
