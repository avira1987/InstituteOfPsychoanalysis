# Deploy anistito to internet host
# Target: https://bpms.psychoanalysis.ir/anistito/

$HostIP = "80.191.11.129"
$HostPort = 2022
$HostUser = "root"
$HostPass = "parsbpms.com"
$RemotePath = "/opt/anistito"

$ErrorActionPreference = "Stop"

Write-Host "=== Step 1: Build admin-ui ===" -ForegroundColor Cyan
Set-Location $PSScriptRoot\admin-ui
& npm run build
if ($LASTEXITCODE -ne 0) { throw "Build failed" }

Write-Host "`n=== Step 2: Create deploy package ===" -ForegroundColor Cyan
Set-Location $PSScriptRoot
$archivePath = Join-Path $env:TEMP "deploy-anistito.zip"

$tempDir = Join-Path $env:TEMP "anistito-deploy"
if (Test-Path $tempDir) { Remove-Item -Recurse -Force $tempDir }
New-Item -ItemType Directory -Path $tempDir | Out-Null

Copy-Item -Path "app" -Destination $tempDir -Recurse -Force
Copy-Item -Path "metadata" -Destination $tempDir -Recurse -Force
Copy-Item -Path "alembic" -Destination $tempDir -Recurse -Force
Copy-Item -Path "scripts" -Destination $tempDir -Recurse -Force
New-Item -ItemType Directory -Path "$tempDir\admin-ui" -Force | Out-Null
Copy-Item -Path "admin-ui\dist" -Destination "$tempDir\admin-ui" -Recurse -Force
Copy-Item -Path "admin-ui\src" -Destination "$tempDir\admin-ui" -Recurse -Force
Copy-Item -Path "admin-ui\index.html","admin-ui\package.json","admin-ui\vite.config.js" -Destination "$tempDir\admin-ui" -Force
if (Test-Path "admin-ui\public") { Copy-Item -Path "admin-ui\public" -Destination "$tempDir\admin-ui" -Recurse -Force }
foreach ($f in @("requirements.txt","Dockerfile","alembic.ini")) { if (Test-Path $f) { Copy-Item $f -Destination $tempDir -Force } }
if (Test-Path ".dockerignore") { Copy-Item ".dockerignore" -Destination $tempDir -Force }

$zipItems = Get-ChildItem $tempDir
Compress-Archive -Path $zipItems.FullName -DestinationPath $archivePath -Force
Remove-Item -Recurse -Force $tempDir -ErrorAction SilentlyContinue
$sizeMB = [math]::Round((Get-Item $archivePath).Length / 1048576, 2)
Write-Host "Created package ($sizeMB MB)" -ForegroundColor Green

Write-Host "`n=== Step 3: Connect and upload ===" -ForegroundColor Cyan

$HostKey = "SHA256:F459aXR14g147aSBxWlTypGEKisuxzYnrYl4kcDyPdA"

# SMS env vars از .env (برای ارسال واقعی پیامک روی هاست)
$smsEnv = ""
if (Test-Path (Join-Path $PSScriptRoot ".env")) {
    Get-Content (Join-Path $PSScriptRoot ".env") -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_ -match '^\s*SMS_PROVIDER=(.+)$') { $smsEnv += " -e SMS_PROVIDER=$($matches[1].Trim())" }
        if ($_ -match '^\s*SMS_API_KEY=(.+)$') { $smsEnv += " -e SMS_API_KEY=$($matches[1].Trim())" }
        if ($_ -match '^\s*SMS_LINE_NUMBER=(.+)$') { $smsEnv += " -e SMS_LINE_NUMBER=$($matches[1].Trim())" }
    }
}
if ($smsEnv) { Write-Host "SMS config from .env will be passed to container" -ForegroundColor Gray }

$pscpPath = $null
$plinkPath = $null
foreach ($p in @("$PSScriptRoot\pscp.exe", "pscp", "C:\Program Files\PuTTY\pscp.exe", "C:\Program Files (x86)\PuTTY\pscp.exe")) {
    if ($p -match "\\" -and (Test-Path $p)) { $pscpPath = $p; break }
    if ($p -notmatch "\\") { $x = Get-Command $p -ErrorAction SilentlyContinue; if ($x) { $pscpPath = $x.Source; break } }
}
foreach ($p in @("$PSScriptRoot\plink.exe", "plink", "C:\Program Files\PuTTY\plink.exe", "C:\Program Files (x86)\PuTTY\plink.exe")) {
    if ($p -match "\\" -and (Test-Path $p)) { $plinkPath = $p; break }
    if ($p -notmatch "\\") { $x = Get-Command $p -ErrorAction SilentlyContinue; if ($x) { $plinkPath = $x.Source; break } }
}

if ($pscpPath -and $plinkPath) {
    Write-Host "Using PuTTY: pscp, plink" -ForegroundColor Gray
    & $pscpPath -P $HostPort -pw $HostPass -hostkey $HostKey $archivePath "${HostUser}@${HostIP}:${RemotePath}/deploy-anistito.zip"
    if ($LASTEXITCODE -ne 0) { throw "Upload failed" }
    Write-Host "`n=== Step 4: Run commands on server ===" -ForegroundColor Cyan
    $cmds = "docker rm -f anistito-api 2>/dev/null; cd $RemotePath && unzip -o deploy-anistito.zip -d . && rm -f deploy-anistito.zip && docker build -t anistito-api . && docker run -d --name anistito-api --network anistito-net -p 8000:8000 -e DATABASE_URL=postgresql+asyncpg://anistito:anistito@anistito-db:5432/anistito -e DATABASE_URL_SYNC=postgresql://anistito:anistito@anistito-db:5432/anistito -e REDIS_URL=redis://anistito-redis:6379/0 -e DEBUG=false -e SECRET_KEY=anistito-prod-secret$smsEnv anistito-api:latest sh -c 'python -m alembic upgrade head 2>/dev/null || true && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000'"
    $ErrorActionPreferenceBak = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $plinkOut = & $plinkPath -P $HostPort -pw $HostPass -hostkey $HostKey -batch "${HostUser}@${HostIP}" $cmds 2>&1
    $ErrorActionPreference = $ErrorActionPreferenceBak
    Write-Host $plinkOut
    Start-Sleep -Seconds 12
    $health = & $plinkPath -P $HostPort -pw $HostPass -hostkey $HostKey -batch "${HostUser}@${HostIP}" "curl -s http://localhost:8000/health" 2>&1
    Write-Host "Health: $health"
} else {
    if (-not (Get-Module Posh-SSH -ErrorAction SilentlyContinue)) {
        Write-Host "Installing Posh-SSH module..." -ForegroundColor Yellow
        Install-Module -Name Posh-SSH -Force -Scope CurrentUser -AllowClobber
    }
    $secPass = ConvertTo-SecureString $HostPass -AsPlainText -Force
    $cred = New-Object System.Management.Automation.PSCredential ($HostUser, $secPass)
    Write-Host "Connecting to ${HostUser}@${HostIP}:${HostPort} ..." -ForegroundColor Gray
    $session = New-SSHSession -ComputerName $HostIP -Port $HostPort -Credential $cred -AcceptKey
    if (-not $session) { throw "SSH connection failed" }
    try {
        Set-SCPItem -ComputerName $HostIP -Port $HostPort -Credential $cred -Path $archivePath -Destination "$RemotePath/deploy-anistito.zip" -AcceptKey
        Write-Host "`n=== Step 4: Run commands on server ===" -ForegroundColor Cyan
        $cmds = "cd $RemotePath; unzip -o deploy-anistito.zip -d .; rm -f deploy-anistito.zip; docker rm -f anistito-api 2>/dev/null || true; docker build -t anistito-api .; docker run -d --name anistito-api --network anistito-net -p 8000:8000 -e DATABASE_URL=postgresql+asyncpg://anistito:anistito@anistito-db:5432/anistito -e DATABASE_URL_SYNC=postgresql://anistito:anistito@anistito-db:5432/anistito -e REDIS_URL=redis://anistito-redis:6379/0 -e DEBUG=false -e SECRET_KEY=anistito-prod-secret$smsEnv anistito-api:latest sh -c 'python -m alembic upgrade head 2>/dev/null || true && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000'; sleep 15; curl -s http://localhost:8000/health || docker logs anistito-api --tail 15"
        $result = Invoke-SSHCommand -SessionId $session.SessionId -Command $cmds -TimeOut 600
        Write-Host $result.Output
        if ($result.Error) { Write-Host $result.Error -ForegroundColor Red }
    }
    finally {
        if ($session) { Remove-SSHSession -SessionId $session.SessionId -ErrorAction SilentlyContinue | Out-Null }
    }
}

Remove-Item $archivePath -Force -ErrorAction SilentlyContinue
Write-Host "`n=== Done ===" -ForegroundColor Green
Write-Host "URL: https://bpms.psychoanalysis.ir/anistito/" -ForegroundColor White
Write-Host "Login: admin / admin123" -ForegroundColor White
