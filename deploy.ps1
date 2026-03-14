# دیپلوی یک‌دست آنیستیتو روی هاست
# اجرا از ریشه پروژه: .\deploy.ps1
# راهنمای کامل: docs\DEPLOY_GUIDE_FA.md

$ErrorActionPreference = "Stop"
$root = if ($PSScriptRoot) { $PSScriptRoot } else { Get-Location }
& "$root\deploy-to-host.ps1"
