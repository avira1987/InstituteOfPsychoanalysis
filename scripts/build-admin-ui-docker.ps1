# بیلد admin-ui داخل کانتینر؛ خروجی در ./admin-ui/dist (همان مسیری که api در docker-compose mount می‌کند)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
# -T: بدون TTY تا خروجی npm روی ویندوز بافر نشود و به‌ظاهر «گیر» نکند
docker compose --profile admin-ui-build run -T --rm admin-ui-build
