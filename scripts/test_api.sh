#!/bin/bash
TOK=$(curl -s -X POST http://127.0.0.1:3000/api/auth/login -d 'username=admin&password=admin123' -H 'Content-Type: application/x-www-form-urlencoded' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "Token OK"
curl -s -H "Authorization: Bearer $TOK" http://127.0.0.1:3000/api/admin/processes/ | python3 -c "import sys,json; d=json.load(sys.stdin); print('Processes:', len(d) if isinstance(d,list) else d)"
echo ""
echo "First 200 chars of response:"
curl -s -H "Authorization: Bearer $TOK" http://127.0.0.1:3000/api/admin/processes/ | head -c 200
