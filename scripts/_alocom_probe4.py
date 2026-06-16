"""Probe 4: full real flow - list services, create event, enroll user, get link."""

import asyncio
import json
import time

import httpx

BASE = "https://pnlapi.alocom.co"
USERNAME = "09032054361"
PASSWORD = "anstitoo@123"


def pp(label, obj):
    try:
        s = json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        s = str(obj)
    print(f"\n=== {label} ===")
    print(s[:4000])


async def login(client):
    r = await client.post(f"{BASE}/api/v1/auth/login", json={"username": USERNAME, "password": PASSWORD})
    r.raise_for_status()
    return r.json()["token"]


async def main():
    async with httpx.AsyncClient(timeout=60.0) as client:
        token = await login(client)
        headers = {"Authorization": f"Bearer {token}"}

        # 1) list agent services
        r = await client.post(
            f"{BASE}/api/v1/agents/agent-services",
            headers=headers,
            json={"take": 50, "skip": 0},
        )
        print("agent-services HTTP", r.status_code)
        services = None
        if r.status_code < 400:
            services = r.json()
            pp("agent-services", services)
        else:
            print("body:", (r.text or "")[:1000])
            return

        # try to extract first service id
        svc_list = (services.get("data") or {}).get("agentServices") or []
        active = [s for s in svc_list if s.get("status") == "active"]
        pp("active services", [(s.get("agentServiceId"), s.get("title")) for s in active])
        if not active:
            print("No ACTIVE service found; stopping before create.")
            return
        service_id = active[0]["agentServiceId"]
        print("\nUsing id_service_agent =", service_id)

        # 2) create event
        slug = f"anistito-probe-{int(time.time())}"
        create_body = {
            "title": "تست اتصال انیستیتو (probe)",
            "slug": slug,
            "agent_service_id": service_id,
            "status": 1,
            "start_by_admin": True,
        }
        r = await client.post(f"{BASE}/api/v1/agents/events", headers=headers, json=create_body)
        print("\ncreate event HTTP", r.status_code)
        try:
            ev = r.json()
        except Exception:
            ev = {"_text": (r.text or "")[:1500]}
        pp("create event response", ev)
        if r.status_code >= 400:
            return

        # extract event id
        eid = None
        d = ev.get("data", ev) if isinstance(ev, dict) else {}
        for cont in (d, d.get("event") if isinstance(d, dict) else None):
            if isinstance(cont, dict):
                for k in ("id", "event_id", "eventId"):
                    if cont.get(k) is not None:
                        eid = cont.get(k)
                        break
            if eid:
                break
        print("\nextracted event id:", eid)
        if not eid:
            return

        # 3) enroll user -> direct link
        r = await client.post(
            f"{BASE}/api/v1/agents/events/{eid}/enroll-user-with-token",
            headers=headers,
            json={
                "name": "دانشجو",
                "surname": "تست",
                "username": f"anistito_probe_{int(time.time())}",
                "role": "participant",
            },
        )
        print("\nenroll HTTP", r.status_code)
        try:
            pp("enroll response", r.json())
        except Exception:
            print("text:", (r.text or "")[:1500])


if __name__ == "__main__":
    asyncio.run(main())
