$ErrorActionPreference = "Stop"
$base = "C:\Users\Administrator\Desktop\anistito"
$tempDir = "$env:TEMP\anistito-pkg"

# 0. Build admin-ui
Push-Location "$base\admin-ui"
& npm run build
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Build failed" }
Pop-Location
$zipPath = "$env:TEMP\deploy-anistito.zip"
$pscp = "$base\pscp.exe"
$plink = "$base\plink.exe"

# 1. Create package
if (Test-Path $tempDir) { Remove-Item -Recurse -Force $tempDir }
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
Copy-Item "$base\app" "$tempDir\app" -Recurse -Force
Copy-Item "$base\metadata" "$tempDir\metadata" -Recurse -Force
Copy-Item "$base\alembic" "$tempDir\alembic" -Recurse -Force
if (Test-Path "$base\scripts") { Copy-Item "$base\scripts" "$tempDir\scripts" -Recurse -Force }
New-Item "$tempDir\admin-ui" -ItemType Directory -Force | Out-Null
Copy-Item "$base\admin-ui\dist" "$tempDir\admin-ui\dist" -Recurse -Force
Copy-Item "$base\admin-ui\src" "$tempDir\admin-ui\src" -Recurse -Force
Copy-Item "$base\admin-ui\index.html","$base\admin-ui\package.json","$base\admin-ui\vite.config.js" "$tempDir\admin-ui" -Force
if (Test-Path "$base\admin-ui\public") { Copy-Item "$base\admin-ui\public" "$tempDir\admin-ui\public" -Recurse -Force }
Copy-Item "$base\requirements.txt","$base\Dockerfile","$base\alembic.ini" "$tempDir" -Force
if (Test-Path "$base\.dockerignore") { Copy-Item "$base\.dockerignore" "$tempDir" -Force }

$items = Get-ChildItem $tempDir
Compress-Archive -Path $items.FullName -DestinationPath $zipPath -Force
Remove-Item -Recurse -Force $tempDir -ErrorAction SilentlyContinue

$hk = "SHA256:F459aXR14g147aSBxWlTypGEKisuxzYnrYl4kcDyPdA"
# 2. Upload
& $pscp -batch -hostkey $hk -P 2022 -pw parsbpms.com $zipPath root@80.191.11.129:/opt/anistito/deploy-anistito.zip

# 3. Run on server
$cmd = 'cd /opt/anistito && unzip -o deploy-anistito.zip -d . && rm -f deploy-anistito.zip && docker rm -f anistito-api; docker build -t anistito-api . && docker run -d --name anistito-api --network anistito-net -p 8000:8000 -e DATABASE_URL=postgresql+asyncpg://anistito:anistito@anistito-db:5432/anistito -e DATABASE_URL_SYNC=postgresql://anistito:anistito@anistito-db:5432/anistito -e REDIS_URL=redis://anistito-redis:6379/0 -e DEBUG=false -e SECRET_KEY=anistito-prod-secret anistito-api:latest && sleep 12 && curl -s http://localhost:8000/health'
& $plink -batch -hostkey $hk -P 2022 -pw parsbpms.com root@80.191.11.129 $cmd
