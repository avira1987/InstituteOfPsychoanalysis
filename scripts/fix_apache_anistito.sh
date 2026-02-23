#!/bin/bash
# Add Anistito ProxyPass to Apache SSL vhost - run on server as root
set -e

CONF="/etc/apache2/sites-available/default-ssl.conf"
BACKUP="/etc/apache2/sites-available/default-ssl.conf.bak.$(date +%Y%m%d%H%M%S)"

if [ ! -f "$CONF" ]; then
  echo "Config not found: $CONF"
  exit 1
fi

if grep -q "ProxyPass.*anistito" "$CONF"; then
  echo "Anistito ProxyPass already in $CONF"
  systemctl reload apache2 2>/dev/null || systemctl reload httpd 2>/dev/null || true
  echo "Done."
  exit 0
fi

cp "$CONF" "$BACKUP"
echo "Backup: $BACKUP"

# Insert before </VirtualHost> using awk
awk '
/^<\/VirtualHost>/ && !done {
  print "	# Anistito BPM - Proxy to FastAPI"
  print "	ProxyPreserveHost On"
  print "	ProxyPass /anistito/api/ http://127.0.0.1:8000/api/"
  print "	ProxyPassReverse /anistito/api/ http://127.0.0.1:8000/api/"
  print "	ProxyPass /anistito/ http://127.0.0.1:8000/"
  print "	ProxyPassReverse /anistito/ http://127.0.0.1:8000/"
  print ""
  done=1
}
{print}
' "$CONF" > "$CONF.new" && mv "$CONF.new" "$CONF"

echo "Added ProxyPass to $CONF"
apache2ctl configtest 2>/dev/null || true
systemctl reload apache2 2>/dev/null || systemctl reload httpd 2>/dev/null || true
echo "Apache reloaded."
