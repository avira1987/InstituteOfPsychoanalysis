# Sync anistito to internet host - code, UI, and database
# Target: https://bpms.psychoanalysis.ir/anistito/

$HostIP = "80.191.11.129"
$HostPort = 2022
$HostUser = "root"
$HostPass = "parsbpms.com"
$RemotePath = "/opt/anistito"

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot

Write-Host "=== Step 1: Export database (SQLite) ===" -ForegroundColor Cyan
$dbPath = Join-Path $projectRoot "anistito.db"
$exportPath = Join-Path $projectRoot "anistito_export.json"

if (Test-Path $dbPath) {
    Set-Location $projectRoot
    python scripts/export_to_online.py
    if ($LASTEXITCODE -ne 0) { throw "Export failed" }
    Write-Host "Exported to anistito_export.json" -ForegroundColor Green
} else {
    Write-Host "SQLite DB not found. Trying PostgreSQL..." -ForegroundColor Yellow
    python scripts/export_from_pg.py
    if ($LASTEXITCODE -ne 0) { throw "Export failed" }
}

if (-not (Test-Path $exportPath)) {
    throw "Export file not created: anistito_export.json"
}

Write-Host "`n=== Step 2: Build admin-ui ===" -ForegroundColor Cyan
Set-Location $projectRoot\admin-ui
& npm run build
if ($LASTEXITCODE -ne 0) { throw "Build failed" }

Write-Host "`n=== Step 3: Create deploy package ===" -ForegroundColor Cyan
Set-Location $projectRoot
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

Write-Host "`n=== Step 4: Connect and upload ===" -ForegroundColor Cyan

$HostKey = "SHA256:F459aXR14g147aSBxWlTypGEKisuxzYnrYl4kcDyPdA"
$pscpPath = $null
$plinkPath = $null
foreach ($p in @("$projectRoot\pscp.exe", "pscp", "C:\Program Files\PuTTY\pscp.exe", "C:\Program Files (x86)\PuTTY\pscp.exe")) {
    if ($p -match "\\" -and (Test-Path $p)) { $pscpPath = $p; break }
    if ($p -notmatch "\\") { $x = Get-Command $p -ErrorAction SilentlyContinue; if ($x) { $pscpPath = $x.Source; break } }
}
foreach ($p in @("$projectRoot\plink.exe", "plink", "C:\Program Files\PuTTY\plink.exe", "C:\Program Files (x86)\PuTTY\plink.exe")) {
    if ($p -match "\\" -and (Test-Path $p)) { $plinkPath = $p; break }
    if ($p -notmatch "\\") { $x = Get-Command $p -ErrorAction SilentlyContinue; if ($x) { $plinkPath = $x.Source; break } }
}

if (-not $pscpPath -or -not $plinkPath) {
    Write-Host "PuTTY (pscp/plink) not found. Trying Posh-SSH..." -ForegroundColor Yellow
    if (-not (Get-Module Posh-SSH -ErrorAction SilentlyContinue)) {
        Install-Module -Name Posh-SSH -Force -Scope CurrentUser -AllowClobber
    }
    $secPass = ConvertTo-SecureString $HostPass -AsPlainText -Force
    $cred = New-Object System.Management.Automation.PSCredential ($HostUser, $secPass)
    Write-Host "Uploading package..." -ForegroundColor Gray
    Set-SCPItem -ComputerName $HostIP -Port $HostPort -Credential $cred -Path $archivePath -Destination "$RemotePath/deploy-anistito.zip" -AcceptKey
    Write-Host "Uploading export..." -ForegroundColor Gray
    Set-SCPItem -ComputerName $HostIP -Port $HostPort -Credential $cred -Path $exportPath -Destination "/tmp/anistito_export.json" -AcceptKey
    Write-Host "`n=== Step 5: Run import and deploy on server ===" -ForegroundColor Cyan
    $session = New-SSHSession -ComputerName $HostIP -Port $HostPort -Credential $cred -AcceptKey
    if (-not $session) { throw "SSH connection failed" }
    try {
        $unzipCmd = "cd $RemotePath && unzip -o deploy-anistito.zip -d . && rm -f deploy-anistito.zip"
        $importCmd = "docker run --rm --network anistito-net -v /opt/anistito:/app -v /tmp:/tmp -w /app -e DATABASE_URL=postgresql+asyncpg://anistito:anistito@anistito-db:5432/anistito python:3.12-slim sh -c 'pip install sqlalchemy asyncpg -q && python scripts/truncate_and_import.py /tmp/anistito_export.json'"
        $deployCmd = "cd $RemotePath && docker rm -f anistito-api 2>/dev/null || true && docker build -t anistito-api . && docker run -d --name anistito-api --network anistito-net -p 3000:3000 -e DATABASE_URL=postgresql+asyncpg://anistito:anistito@anistito-db:5432/anistito -e DATABASE_URL_SYNC=postgresql://anistito:anistito@anistito-db:5432/anistito -e REDIS_URL=redis://anistito-redis:6379/0 -e DEBUG=false -e SECRET_KEY=anistito-prod-secret anistito-api:latest sh -c 'python -m alembic upgrade head 2>/dev/null || true && python -m uvicorn app.main:app --host 0.0.0.0 --port 3000'"
        Invoke-SSHCommand -SessionId $session.SessionId -Command $unzipCmd -TimeOut 60 | Out-Null
        $result = Invoke-SSHCommand -SessionId $session.SessionId -Command $importCmd -TimeOut 120
        Write-Host $result.Output
        $result2 = Invoke-SSHCommand -SessionId $session.SessionId -Command $deployCmd -TimeOut 600
        Write-Host $result2.Output
        Start-Sleep -Seconds 15
        $health = Invoke-SSHCommand -SessionId $session.SessionId -Command "curl -s http://localhost:3000/health" -TimeOut 10
        Write-Host "Health: $($health.Output)"
    }
    finally {
        Remove-SSHSession -SessionId $session.SessionId -ErrorAction SilentlyContinue | Out-Null
    }
} else {
    Write-Host "Using PuTTY: pscp, plink" -ForegroundColor Gray
    & $pscpPath -P $HostPort -pw $HostPass -hostkey $HostKey $archivePath "${HostUser}@${HostIP}:${RemotePath}/deploy-anistito.zip"
    if ($LASTEXITCODE -ne 0) { throw "Package upload failed" }
    & $pscpPath -P $HostPort -pw $HostPass -hostkey $HostKey $exportPath "${HostUser}@${HostIP}:/tmp/anistito_export.json"
    if ($LASTEXITCODE -ne 0) { throw "Export upload failed" }

    Write-Host "`n=== Step 5: Unzip and import data on server ===" -ForegroundColor Cyan
    $unzipCmd = "cd $RemotePath && unzip -o deploy-anistito.zip -d . && rm -f deploy-anistito.zip"
    $ErrorActionPreferenceBak = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $plinkPath -P $HostPort -pw $HostPass -hostkey $HostKey -batch "${HostUser}@${HostIP}" $unzipCmd 2>&1 | Out-Null

    $importCmd = "docker run --rm --network anistito-net -v /opt/anistito:/app -v /tmp:/tmp -w /app -e DATABASE_URL=postgresql+asyncpg://anistito:anistito@anistito-db:5432/anistito python:3.12-slim sh -c 'pip install sqlalchemy asyncpg -q && python scripts/truncate_and_import.py /tmp/anistito_export.json'"
    $importOut = & $plinkPath -P $HostPort -pw $HostPass -hostkey $HostKey -batch "${HostUser}@${HostIP}" $importCmd 2>&1
    $ErrorActionPreference = $ErrorActionPreferenceBak
    Write-Host $importOut

    Write-Host "`n=== Step 6: Deploy code on server ===" -ForegroundColor Cyan
    $deployCmd = "cd $RemotePath && docker rm -f anistito-api 2>/dev/null || true && docker build -t anistito-api . && docker run -d --name anistito-api --network anistito-net -p 3000:3000 -e DATABASE_URL=postgresql+asyncpg://anistito:anistito@anistito-db:5432/anistito -e DATABASE_URL_SYNC=postgresql://anistito:anistito@anistito-db:5432/anistito -e REDIS_URL=redis://anistito-redis:6379/0 -e DEBUG=false -e SECRET_KEY=anistito-prod-secret anistito-api:latest sh -c 'python -m alembic upgrade head 2>/dev/null || true && python -m uvicorn app.main:app --host 0.0.0.0 --port 3000'"
    $ErrorActionPreference = "SilentlyContinue"
    $deployOut = & $plinkPath -P $HostPort -pw $HostPass -hostkey $HostKey -batch "${HostUser}@${HostIP}" $deployCmd 2>&1
    $ErrorActionPreference = $ErrorActionPreferenceBak
    Write-Host $deployOut
    Start-Sleep -Seconds 12
    $health = & $plinkPath -P $HostPort -pw $HostPass -hostkey $HostKey -batch "${HostUser}@${HostIP}" "curl -s http://localhost:3000/health" 2>&1
    Write-Host "Health: $health"
}

Remove-Item $archivePath -Force -ErrorAction SilentlyContinue
Write-Host "`n=== Sync Complete ===" -ForegroundColor Green
Write-Host "URL: https://bpms.psychoanalysis.ir/anistito/" -ForegroundColor White
Write-Host "Login: admin / admin123  |  student1 / demo123  |  staff1 / demo123  |  ..." -ForegroundColor White
