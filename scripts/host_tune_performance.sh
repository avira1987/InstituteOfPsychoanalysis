#!/bin/bash
# بهبود پایداری: تایم‌اوت پروکسی Apache + فشرده‌سازی (swap در بعضی LXC/Proxmox غیرمجاز است)
# اجرا با: bash scripts/host_tune_performance.sh
set -euo pipefail

echo "=== Apache: تایم‌اوت پروکسی و فشرده‌سازی ==="
a2enmod deflate 2>/dev/null || true

CONF=/etc/apache2/conf-available/anistito-performance.conf
cat >"$CONF" <<'EOF'
# جلوگیری از آویزان ماندن اتصال به بک‌اند
Timeout 120
ProxyTimeout 120

<IfModule mod_deflate.c>
  AddOutputFilterByType DEFLATE text/html text/plain text/xml text/css application/javascript application/json
</IfModule>
EOF
a2enconf anistito-performance 2>/dev/null || true

apache2ctl configtest
systemctl reload apache2
echo "Apache performance conf OK"

echo "=== حذف فرآیندهای curl گیرکرده (تشخیص قدیمی) ==="
pkill -f "curl.*lms.psychoanalysis" 2>/dev/null || true
echo "پایان."
