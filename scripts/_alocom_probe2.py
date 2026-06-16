"""Probe 2: find agent's own service id and event-list shape (read-only)."""

import asyncio
import json

import httpx

BASE = "https://pnlapi.alocom.co"
USERNAME = "09032054361"
PASSWORD = "anstitoo@123"

GET_PATHS = [
    "/api/v1/agent/me",
    "/api/v1/agent/profile",
    "/api/v1/agent/info",
    "/api/v1/agent/dashboard",
    "/api/v1/agent/credit",
    "/api/v1/agent/credits",
    "/api/v1/agent/wallet",
    "/api/v1/agent/services/my",
    "/api/v1/agent/my-services",
    "/api/v1/agent/purchased-services",
    "/api/v1/agent/service-credits",
    "/api/v1/agent/event",
    "/api/v1/agent/events",
    "/api/v1/agent/event/list",
    "/api/v1/me",
    "/api/v1/profile",
]


def short(obj, n=2000):
    try:
        s = json.dumps(obj, ensure_ascii=False)
    except Exception:
        s = str(obj)
    return s[:n]


async def login(client):
    r = await client.post(f"{BASE}/api/v1/auth/login", json={"username": USERNAME, "password": PASSWORD})
    return r.json()["token"]


async def main():
    async with httpx.AsyncClient(timeout=40.0) as client:
        token = await login(client)
        headers = {"Authorization": f"Bearer {token}"}
        for p in GET_PATHS:
            url = f"{BASE}{p}"
            try:
                r = await client.get(url, headers=headers)
            except Exception as e:
                print(f"GET {p} -> EXC {e}")
                continue
            print(f"GET {p} -> HTTP {r.status_code}")
            if r.status_code < 400 and r.content:
                try:
                    print("   ", short(r.json()))
                except Exception:
                    print("    text:", (r.text or "")[:600])


if __name__ == "__main__":
    asyncio.run(main())
