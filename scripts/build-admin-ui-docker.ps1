# بیلد admin-ui داخل کانتینر؛ خروجی در ./admin-ui/dist (همان مسیری که api در docker-compose mount می‌کند)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
docker compose --profile admin-ui-build run --rm admin-ui-build
