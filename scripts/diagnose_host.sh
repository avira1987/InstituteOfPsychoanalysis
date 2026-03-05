#!/bin/bash
# تشخیص مشکل Service Unavailable روی سرور
# اجرا: ssh -p 2022 root@80.191.11.129 "bash -s" < scripts/diagnose_host.sh

echo "=== 1. وضعیت کانتینر anistito-api ==="
docker ps -a --filter name=anistito-api --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "=== 2. لاگ‌های آخر کانتینر (اگر وجود دارد) ==="
docker logs anistito-api --tail 50 2>&1 || echo "(کانتینر وجود ندارد یا خطا)"

echo ""
echo "=== 3. پورت 8000 در حال گوش دادن؟ ==="
ss -tlnp | grep 8000 || netstat -tlnp 2>/dev/null | grep 8000 || echo "پورت 8000 باز نیست"

echo ""
echo "=== 4. تست مستقیم health ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:8000/health 2>&1 || echo "curl failed"

echo ""
echo "=== 5. وضعیت شبکه Docker ==="
docker network ls | grep anistito

echo ""
echo "=== 6. کانتینرهای مرتبط ==="
docker ps -a --filter network=anistito-net --format "table {{.Names}}\t{{.Status}}"

echo ""
echo "=== 7. Apache ProxyPass برای anistito ==="
grep -r "anistito" /etc/apache2/sites-enabled/ /etc/apache2/sites-available/ 2>/dev/null | head -20 || grep -r "anistito" /etc/httpd/conf.d/ 2>/dev/null | head -20
