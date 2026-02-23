# Deploy Anistito to internet server
# Run from project root: .\deploy-to-server.ps1
# Uses ssh/scp (OpenSSH) - enter password when prompted

$SERVER = "80.191.11.129"
$PORT = "2022"
$USER = "root"
$REMOTE_PATH = "/opt/anistito"
$target = "${USER}@${SERVER}:${REMOTE_PATH}/"

Write-Host "=== 1. Building Admin UI locally ===" -ForegroundColor Cyan
Push-Location admin-ui
npm run build
if ($LASTEXITCODE -ne 0) { Pop-Location; exit 1 }
Pop-Location

Write-Host "`n=== 2. Uploading to server (password may be asked) ===" -ForegroundColor Cyan
scp -r -P $PORT app admin-ui metadata alembic scripts requirements.txt Dockerfile docker-compose.yml deploy-server.sh $target
if ($LASTEXITCODE -ne 0) { Write-Host "Upload failed." -ForegroundColor Red; exit 1 }

Write-Host "`n=== 3. Rebuilding on server ===" -ForegroundColor Cyan
$cmd = "cd $REMOTE_PATH && docker rm -f anistito-api 2>/dev/null || true && docker build -t anistito-api . && docker run -d --name anistito-api --network anistito-net -p 8000:8000 -e DATABASE_URL=postgresql+asyncpg://anistito:anistito@anistito-db:5432/anistito -e DATABASE_URL_SYNC=postgresql://anistito:anistito@anistito-db:5432/anistito -e REDIS_URL=redis://anistito-redis:6379/0 -e DEBUG=false -e SECRET_KEY=anistito-prod-secret anistito-api:latest sh -c 'python -m alembic upgrade head 2>/dev/null || true && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000' && sleep 12 && echo '=== Test process count ===' && curl -s http://localhost:8000/debug/process-count"
ssh -p $PORT ${USER}@${SERVER} $cmd

Write-Host "`n=== Done. Check https://lms.psychoanalysis.ir/anistito/ ===" -ForegroundColor Green
