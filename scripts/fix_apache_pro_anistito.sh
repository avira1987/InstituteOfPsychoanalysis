#!/bin/bash
# Add /anistito/api/ ProxyPass to pro.conf - run on server as root
# The more specific /anistito/api/ rule ensures API redirects are rewritten correctly
set -e

CONF="/etc/apache2/sites-available/pro.conf"
[ ! -f "$CONF" ] && { echo "pro.conf not found"; exit 1; }

if grep -q "ProxyPass /anistito/api/" "$CONF"; then
  echo "Anistito /anistito/api/ already configured"
  systemctl reload apache2 2>/dev/null || systemctl reload httpd 2>/dev/null || true
  exit 0
fi

BACKUP="${CONF}.bak.$(date +%Y%m%d%H%M%S)"
cp "$CONF" "$BACKUP"
echo "Backup: $BACKUP"

# Insert /anistito/api/ rules BEFORE the general /anistito/ (order matters)
sed -i '/ProxyPass \/anistito\//i\    # Anistito API (more specific - before /anistito/)\n    ProxyPass /anistito/api/ http://127.0.0.1:3000/api/\n    ProxyPassReverse /anistito/api/ http://127.0.0.1:3000/api/\n    ProxyPassReverse /anistito/api/ http://localhost:3000/api/' "$CONF"

apache2ctl configtest 2>/dev/null || true
systemctl reload apache2 2>/dev/null || systemctl reload httpd 2>/dev/null || true
echo "Apache reloaded."
