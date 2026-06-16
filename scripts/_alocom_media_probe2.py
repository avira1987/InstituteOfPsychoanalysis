"""Probe participant enroll order and start_by_admin."""

from __future__ import annotations

import asyncio
import json
import time
import uuid

import httpx

from app.config import get_settings
from app.services.alocom_client import _extract_register_link


async def enroll(c, s, h, eid: str, role: str, label: str) -> dict:
    uname = f"{label}_{role}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
    r = await c.post(
        f"{s.ALOCOM_API_BASE}{s.ALOCOM_PATH_REGISTER_IN_EVENT.format(event_id=eid)}",
        headers=h,
        json={
            "name": "کاربر",
            "surname": "تست",
            "username": uname,
            "role": role,
            "cellphone": "09123456789",
        },
    )
    body = r.json() if r.content else {}
    return {
        "status": r.status_code,
        "message": body.get("message") if isinstance(body, dict) else None,
        "link": _extract_register_link(body if isinstance(body, dict) else {}),
    }


async def scenario(c, s, h, *, start_by_admin: int, teacher_first: bool) -> dict:
    slug = f"probe-{start_by_admin}-{int(time.time())}-{uuid.uuid4().hex[:4]}"
    ev = (
        await c.post(
            f"{s.ALOCOM_API_BASE}{s.ALOCOM_PATH_CREATE_EVENT}",
            headers=h,
            json={
                "title": f"media probe {uuid.uuid4().hex[:8]}",
                "slug": slug,
                "agent_service_id": int(s.ALOCOM_DEFAULT_AGENT_SERVICE_ID),
                "status": 1,
                "start_by_admin": start_by_admin,
                "guest_access": True,
            },
        )
    ).json()
    eid = str((ev.get("event") or {}).get("id") or "")
    out = {
        "start_by_admin": start_by_admin,
        "teacher_first": teacher_first,
        "event_id": eid,
        "class_link": (ev.get("event") or {}).get("alocom_link"),
    }
    if not eid:
        out["create_error"] = ev
        return out
    order = ("teacher", "participant") if teacher_first else ("participant", "teacher")
    for role in order:
        out[f"enroll_{role}"] = await enroll(c, s, h, eid, role, f"s{start_by_admin}")
    return out


async def main() -> None:
    s = get_settings()
    results = []
    async with httpx.AsyncClient(timeout=60) as c:
        tok = (
            await c.post(
                f"{s.ALOCOM_API_BASE}{s.ALOCOM_PATH_LOGIN}",
                json={"username": s.ALOCOM_USERNAME, "password": s.ALOCOM_PASSWORD},
            )
        ).json()["token"]
        h = {"Authorization": f"Bearer {tok}"}
        for sab in (0, 1):
            for tf in (True, False):
                results.append(await scenario(c, s, h, start_by_admin=sab, teacher_first=tf))
    with open("_alocom_media_probe2.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("done")


if __name__ == "__main__":
    asyncio.run(main())
