#!/bin/bash
# Check Apache proxy config for Anistito - run on server
echo "=== Checking Apache config for /anistito/ ==="
grep -r "anistito" /etc/apache2/sites-enabled/ /etc/httpd/conf.d/ 2>/dev/null || true
echo ""
echo "=== Testing API endpoints ==="
curl -s -o /dev/null -w "GET /anistito/health: %{http_code}\n" http://localhost:8000/health
curl -s -o /dev/null -w "GET /anistito/api/admin/processes/ (no auth): %{http_code}\n" -H "Accept: application/json" http://localhost:8000/api/admin/processes/
echo "Expected: health=200, processes=401 (unauthorized)"
