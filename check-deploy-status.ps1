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
if (-not $plinkPath) { Write-Host "plink not found"; exit 1 }

$cmd = "docker ps -a; echo '---'; docker images anistito*; echo '---'; ls -la /opt/anistito/app/main.py 2>&1; echo '---'; docker logs anistito-api --tail 30 2>&1 || true"
$out = & $plinkPath -P $HostPort -pw $HostPass -hostkey $HostKey -batch "${HostUser}@${HostIP}" $cmd 2>&1
Write-Host $out
