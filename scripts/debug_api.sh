#!/bin/bash
curl -s -w "\nHTTP_LOGIN:%{http_code}" -X POST http://127.0.0.1:8000/api/auth/login -d "username=admin&password=admin123" -H "Content-Type: application/x-www-form-urlencoded" -o /tmp/login.json
TOK=$(python3 -c "import json; print(json.load(open('/tmp/login.json'))['access_token'])")
echo "Token len: ${#TOK}"
curl -s -w "\nHTTP_PROC:%{http_code}" -H "Authorization: Bearer $TOK" http://127.0.0.1:8000/api/admin/processes/ -o /tmp/proc.json
echo "Proc response:"
cat /tmp/proc.json
echo ""
