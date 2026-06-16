"""Probe 5: try enroll-user-with-token variations on a fresh event."""

import asyncio
import json
import time

import httpx

BASE = "https://pnlapi.alocom.co"
USERNAME = "09032054361"
PASSWORD = "anstitoo@123"
SERVICE_ID = 138048


def pp(label, obj):
    print(f"\n=== {label} ===")
    try:
        print(json.dumps(obj, ensure_ascii=False, indent=2)[:2500])
    except Exception:
        print(str(obj)[:2500])


async def main():
    async with httpx.AsyncClient(timeout=60.0) as client:
        tok = (await client.post(f"{BASE}/api/v1/auth/login",
               json={"username": USERNAME, "password": PASSWORD})).json()["token"]
        h = {"Authorization": f"Bearer {tok}"}

        slug = f"anistito-probe-{int(time.time())}"
        ev = (await client.post(f"{BASE}/api/v1/agents/events", headers=h, json={
            "title": "تست enroll", "slug": slug, "agent_service_id": SERVICE_ID,
            "status": 1, "start_by_admin": False, "guest_access": True,
        })).json()
        eid = ev["event"]["id"]
        print("event id:", eid, "class link:", ev["event"].get("alocom_link"))

        async def enroll(role, uname, extra=None):
            body = {"name": "کاربر", "surname": role, "username": uname, "role": role}
            if extra:
                body.update(extra)
            r = await client.post(
                f"{BASE}/api/v1/agents/events/{eid}/enroll-user-with-token",
                headers=h, json=body)
            print(f"\nenroll role={role} HTTP {r.status_code}")
            try:
                pp("resp", r.json())
            except Exception:
                print((r.text or "")[:800])

        await enroll("teacher", f"anistito_t_{int(time.time())}")
        await enroll("participant", f"anistito_p_{int(time.time())}")
        # try with mobile field
        await enroll("participant", f"anistito_p2_{int(time.time())}", {"mobile": "09120000000", "cellphone": "09120000000"})


if __name__ == "__main__":
    asyncio.run(main())
