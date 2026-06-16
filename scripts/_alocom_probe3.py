"""Probe 3: dump full /api/v1/services and probe doc/swagger + alt event paths."""

import asyncio
import json

import httpx

BASE = "https://pnlapi.alocom.co"
USERNAME = "09032054361"
PASSWORD = "anstitoo@123"


async def login(client):
    r = await client.post(f"{BASE}/api/v1/auth/login", json={"username": USERNAME, "password": PASSWORD})
    return r.json()["token"]


GET_PATHS = [
    "/api/v1/services",
    "/api/documentation",
    "/api/v1/documentation",
    "/docs",
    "/swagger",
    "/api/swagger.json",
    "/api/v1/event",
    "/api/v1/events",
    "/api/v1/class",
    "/api/v1/classes",
    "/api/v1/agent/class",
]


async def main():
    async with httpx.AsyncClient(timeout=40.0, follow_redirects=True) as client:
        token = await login(client)
        headers = {"Authorization": f"Bearer {token}"}
        for p in GET_PATHS:
            try:
                r = await client.get(f"{BASE}{p}", headers=headers)
            except Exception as e:
                print(f"GET {p} -> EXC {e}")
                continue
            ct = r.headers.get("content-type", "")
            print(f"GET {p} -> HTTP {r.status_code} ({ct})")
            if r.status_code < 400 and r.content:
                if "json" in ct:
                    print("   ", json.dumps(r.json(), ensure_ascii=False)[:3000])
                else:
                    print("    text:", (r.text or "")[:300])


if __name__ == "__main__":
    asyncio.run(main())
