#!/bin/bash
# پس از بیلد Docker با SOCKS: قطع xray/v2ray تا میزبان و سرویس‌ها با شبکهٔ عادی کار کنند.
# (کانتینر anistito-api به‌طور پیش‌فرض از پروکسی میزبان استفاده نمی‌کند.)
set -euo pipefail
for svc in xray v2ray; do
  if systemctl is-active --quiet "${svc}" 2>/dev/null; then
    systemctl stop "${svc}"
    echo "Stopped ${svc}.service"
  fi
done
echo "OK: پروکسی متوقف شد (در صورت وجود سرویس)."
