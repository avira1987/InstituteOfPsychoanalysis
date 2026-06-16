"""Probe Alocom roles for mic/camera-capable join links."""

from __future__ import annotations

import asyncio
import json
import time
import uuid

import httpx

from app.config import get_settings
from app.services.alocom_client import _extract_register_link


async def main() -> None:
    s = get_settings()
    out: dict = {}
    async with httpx.AsyncClient(timeout=60) as c:
        tok = (
            await c.post(
                f"{s.ALOCOM_API_BASE}{s.ALOCOM_PATH_LOGIN}",
                json={"username": s.ALOCOM_USERNAME, "password": s.ALOCOM_PASSWORD},
            )
        ).json()["token"]
        h = {"Authorization": f"Bearer {tok}"}

        users = []
        for role in ("participant", "teacher"):
            uname = f"probe_{role}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
            cu = (
                await c.post(
                    f"{s.ALOCOM_API_BASE}{s.ALOCOM_PATH_CREATE_USER}",
                    headers=h,
                    json={
                        "name": "Test",
                        "surname": role,
                        "username": uname,
                        "status": 1,
                        "cellphone": "09121111111",
                    },
                )
            ).json()
            data = cu.get("data") if isinstance(cu.get("data"), dict) else cu
            uid = data.get("id") or data.get("userId")
            users.append({"uname": uname, "uid": uid, "role": role})

        out["created_users"] = users
        slug = f"users-at-create-{int(time.time())}"
        ev = (
            await c.post(
                f"{s.ALOCOM_API_BASE}{s.ALOCOM_PATH_CREATE_EVENT}",
                headers=h,
                json={
                    "title": f"users create {uuid.uuid4().hex[:8]}",
                    "slug": slug,
                    "agent_service_id": int(s.ALOCOM_DEFAULT_AGENT_SERVICE_ID),
                    "status": 1,
                    "start_by_admin": 1,
                    "users": [{"userid": u["uid"], "role": u["role"]} for u in users if u["uid"]],
                },
            )
        ).json()
        eid = str((ev.get("event") or {}).get("id") or "")
        out["event_id"] = eid
        out["class_link"] = (ev.get("event") or {}).get("alocom_link")
        out["create_keys"] = list(ev.keys())

        if eid:
            for u in users:
                r = await c.post(
                    f"{s.ALOCOM_API_BASE}{s.ALOCOM_PATH_REGISTER_IN_EVENT.format(event_id=eid)}",
                    headers=h,
                    json={
                        "name": "Test",
                        "surname": u["role"],
                        "username": u["uname"],
                        "role": u["role"],
                        "cellphone": "09121111111",
                    },
                )
                body = r.json() if r.content else {}
                out[f"enroll_existing_{u['role']}"] = {
                    "status": r.status_code,
                    "link": _extract_register_link(body if isinstance(body, dict) else {}),
                    "message": body.get("message") if isinstance(body, dict) else None,
                }

            for role in ("student", "user", "member", "client", "assistant"):
                r = await c.post(
                    f"{s.ALOCOM_API_BASE}{s.ALOCOM_PATH_REGISTER_IN_EVENT.format(event_id=eid)}",
                    headers=h,
                    json={
                        "name": "St",
                        "surname": "U",
                        "username": f"{role}{int(time.time())}",
                        "role": role,
                    },
                )
                body = r.json() if r.content else {}
                out[f"role_try_{role}"] = {
                    "status": r.status_code,
                    "message": body.get("message") if isinstance(body, dict) else None,
                    "link": _extract_register_link(body if isinstance(body, dict) else {}),
                }

    with open("_alocom_users_probe.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("wrote _alocom_users_probe.json")


if __name__ == "__main__":
    asyncio.run(main())
