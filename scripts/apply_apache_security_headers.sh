#!/bin/bash
# هدرهای امنیتی + HSTS فقط روی SSL — روی هاست اجرا شود
set -euo pipefail

CONF="/etc/apache2/conf-available/anistito-security-headers.conf"
cat >"$CONF" <<'EOF'
<IfModule mod_headers.c>
  Header always set X-Frame-Options "SAMEORIGIN"
  Header always set X-Content-Type-Options "nosniff"
  Header always set Referrer-Policy "strict-origin-when-cross-origin"
  Header always set Permissions-Policy "geolocation=(), microphone=(), camera=(), payment=()"
  Header always set Cross-Origin-Opener-Policy "same-origin"
</IfModule>
LimitRequestBody 26214400
EOF

a2enmod headers 2>/dev/null || true
a2enconf anistito-security-headers 2>/dev/null || true

SSLF=/etc/apache2/sites-available/psychosites-ssl.conf
if [ -f "$SSLF" ] && ! grep -q 'Strict-Transport-Security' "$SSLF"; then
  sed -i '/SSLEngine on/a\    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"' "$SSLF"
fi

apache2ctl configtest
systemctl reload apache2
echo "OK: Apache security + HSTS (if SSL site present)"
