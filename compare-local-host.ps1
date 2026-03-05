# Compare local vs remote host - single SSH call for all hashes
$HostIP = "80.191.11.129"
$HostPort = 2022
$HostUser = "root"
$HostPass = "parsbpms.com"
$RemotePath = "/opt/anistito"
$HostKey = "SHA256:F459aXR14g147aSBxWlTypGEKisuxzYnrYl4kcDyPdA"

$plinkPath = $null
foreach ($p in @("$PSScriptRoot\plink.exe", "C:\Program Files\PuTTY\plink.exe", "plink")) {
    if ($p -match "\\" -and (Test-Path $p)) { $plinkPath = $p; break }
    if ($p -notmatch "\\") { $x = Get-Command $p -ErrorAction SilentlyContinue; if ($x) { $plinkPath = $x.Source; break } }
}
if (-not $plinkPath) { Write-Host "plink not found"; exit 1 }

$files = "app/main.py app/api/auth_routes.py app/api/student/routes.py app/config.py app/models/operational_models.py app/api/blog_routes.py app/api/public_routes.py app/services/otp_service.py admin-ui/src/App.jsx admin-ui/src/components/Layout.jsx admin-ui/src/components/PublicLayout.jsx admin-ui/src/contexts/AuthContext.jsx admin-ui/src/pages/Dashboard.jsx admin-ui/src/pages/LoginPage.jsx admin-ui/src/pages/ProcessEditor.jsx admin-ui/src/pages/ProcessList.jsx admin-ui/src/pages/StudentPortal.jsx admin-ui/src/pages/SupervisorPortal.jsx admin-ui/src/pages/CommitteePortal.jsx admin-ui/src/pages/SiteManagerPortal.jsx admin-ui/src/pages/StaffPortal.jsx admin-ui/src/pages/TherapistPortal.jsx admin-ui/src/services/api.js admin-ui/src/styles/global.css alembic/env.py"
$cmd = "cd $RemotePath && for f in $files; do [ -f `"`$f`" ] && md5sum `"`$f`" || echo MISSING:`$f; done"
$remoteOut = & $plinkPath -P $HostPort -pw $HostPass -hostkey $HostKey -batch "${HostUser}@${HostIP}" $cmd 2>$null

$remoteHashes = @{}
foreach ($line in ($remoteOut -split "`n")) {
    if ($line -match '^([a-f0-9]{32})\s+(.+)$') { $remoteHashes[$matches[2].Trim()] = $matches[1] }
    elseif ($line -match '^MISSING:(.+)$') { $remoteHashes[$matches[1].Trim()] = $null }
}

# Check public dir
$pubCheck = & $plinkPath -P $HostPort -pw $HostPass -hostkey $HostKey -batch "${HostUser}@${HostIP}" "test -d $RemotePath/admin-ui/src/pages/public && echo EXISTS || echo MISSING" 2>$null

$newOnLocal = @()
$modified = @()
$root = $PSScriptRoot

$allFiles = $files -split '\s+'
foreach ($f in $allFiles) {
    $localPath = Join-Path $root ($f -replace '/','\')
    $existsLocal = Test-Path $localPath
    $rh = $remoteHashes[$f]
    $existsRemote = $null -ne $rh
    if ($existsLocal) {
        $localHash = (Get-FileHash -Path $localPath -Algorithm MD5).Hash.ToLower()
        if (-not $existsRemote) { $newOnLocal += $f }
        elseif ($localHash -ne $rh.ToLower()) { $modified += $f }
    }
}

if ((Test-Path (Join-Path $root "admin-ui\src\pages\public")) -and $pubCheck -match "MISSING") { $newOnLocal += "admin-ui/src/pages/public/" }

Write-Host "`n=== NEW on Local (not on Host) ===" -ForegroundColor Yellow
$newOnLocal | ForEach-Object { Write-Host "  + $_" }
if ($newOnLocal.Count -eq 0) { Write-Host "  (none)" }

Write-Host "`n=== MODIFIED (different content) ===" -ForegroundColor Yellow
$modified | ForEach-Object { Write-Host "  ~ $_" }
if ($modified.Count -eq 0) { Write-Host "  (none)" }

Write-Host "`nTotal: $($newOnLocal.Count + $modified.Count) differences" -ForegroundColor Cyan
