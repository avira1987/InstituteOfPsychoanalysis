#!/bin/bash
# اجرا روی سرور (root) در /opt/anistito — دیتابیس Docker پاک نمی‌شود.
set -euo pipefail

APACHE_LMS="/etc/apache2/sites-available/lms-psychoanalysis.conf"
APP_DIR="${1:-/opt/anistito}"

echo "[1/4] Apache: VirtualHost برای lms.psychoanalysis.ir"
cat > "$APACHE_LMS" << 'EOF'
<VirtualHost *:80>
    ServerName lms.psychoanalysis.ir
    ServerAdmin webmaster@psychoanalysis.ir

    RedirectMatch ^/$ /anistito/

    ProxyPreserveHost On
    ProxyPass /anistito/api/ http://127.0.0.1:3000/api/
    ProxyPassReverse /anistito/api/ http://127.0.0.1:3000/api/
    ProxyPass /anistito/ http://127.0.0.1:3000/
    ProxyPassReverse /anistito/ http://127.0.0.1:3000/

    ErrorLog ${APACHE_LOG_DIR}/lms-psycho-error.log
    CustomLog ${APACHE_LOG_DIR}/lms-psycho-access.log combined
</VirtualHost>
EOF

a2enmod proxy proxy_http headers rewrite ssl 2>/dev/null || true
test -L /etc/apache2/sites-enabled/lms-psychoanalysis.conf || a2ensite lms-psychoanalysis.conf
apache2ctl configtest
systemctl reload apache2

echo "[2/4] Docker: بالا آوردن استک (بدون حذف volume)"
cd "$APP_DIR"
docker-compose up -d

echo "[3/4] تست محلی"
sleep 3
curl -sf "http://127.0.0.1:3000/health" | head -c 200 || true
echo
curl -sI -H 'Host: lms.psychoanalysis.ir' "http://127.0.0.1/anistito/" | head -5 || true

echo "[4/4] اختیاری: گواهی Let's Encrypt (اگر DNS به این سرور است و پورت 80 از اینترنت باز است)"
if command -v certbot >/dev/null 2>&1; then
  certbot --apache -d lms.psychoanalysis.ir --non-interactive --agree-tos --register-unsafely-without-email --redirect 2>&1 | tail -15 || echo "certbot: در صورت خطا، SSL را روی لبهٔ شبکه یا بعداً اجرا کنید."
else
  echo "برای HTTPS: apt install certbot python3-certbot-apache && certbot --apache -d lms.psychoanalysis.ir"
fi

echo "پایان."
