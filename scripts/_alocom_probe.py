"""Temporary probe: verify Alocom login + discover agent_service_id. Safe (read-only)."""

import asyncio
import json

import httpx

BASE = "https://pnlapi.alocom.co"
USERNAME = "09032054361"
PASSWORD = "anstitoo@123"

LOGIN_PATHS = [
    "/api/v1/auth/login",
    "/api/auth/login",
    "/api/login",
    "/api/v1/login",
    "/api/agent/auth/login",
]

SERVICE_LIST_PATHS = [
    "/api/v1/agent/services",
    "/api/v1/agent/service",
    "/api/v1/agent/services/list",
    "/api/v1/agent/service/list",
    "/api/agent/services",
    "/api/v1/services",
    "/api/v1/agent/agent-services",
    "/api/v1/agent/event/services",
]


def short(obj, n=1200):
    try:
        s = json.dumps(obj, ensure_ascii=False)
    except Exception:
        s = str(obj)
    return s[:n]


async def main():
    async with httpx.AsyncClient(timeout=40.0) as client:
        token = None
        good_login = None
        for p in LOGIN_PATHS:
            url = f"{BASE}{p}"
            try:
                r = await client.post(url, json={"username": USERNAME, "password": PASSWORD})
            except Exception as e:
                print(f"[login] {p} -> EXC {e}")
                continue
            print(f"[login] {p} -> HTTP {r.status_code}")
            if r.status_code < 400 and r.content:
                try:
                    data = r.json()
                except Exception:
                    print("   (non-json)", (r.text or "")[:300])
                    continue
                print("   body:", short(data, 600))
                # find token
                def find_tok(d):
                    if not isinstance(d, dict):
                        return None
                    for k in ("token", "access_token", "accessToken"):
                        v = d.get(k)
                        if isinstance(v, str) and v:
                            return v
                    inner = d.get("data")
                    if isinstance(inner, dict):
                        return find_tok(inner)
                    return None
                tok = find_tok(data)
                if tok:
                    token = tok
                    good_login = p
                    print(f"   >>> TOKEN OK via {p}")
                    break
        if not token:
            print("NO TOKEN obtained. Stopping.")
            return
        headers = {"Authorization": f"Bearer {token}"}
        print("\n=== Probing service-list endpoints (GET) ===")
        for p in SERVICE_LIST_PATHS:
            url = f"{BASE}{p}"
            try:
                r = await client.get(url, headers=headers)
            except Exception as e:
                print(f"[svc] GET {p} -> EXC {e}")
                continue
            print(f"[svc] GET {p} -> HTTP {r.status_code}")
            if r.status_code < 400 and r.content:
                try:
                    print("   body:", short(r.json(), 1500))
                except Exception:
                    print("   text:", (r.text or "")[:400])
        print("\nGood login path:", good_login)


if __name__ == "__main__":
    asyncio.run(main())
