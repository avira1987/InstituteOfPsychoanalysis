"""ضبط پیامک‌های شبیه‌سازی‌شده در هر درخواست API و الحاق به پاسخ JSON برای پاپ‌آپ فوری."""

from __future__ import annotations

import json
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.services import sms_simulation_service as sms_sim

logger = logging.getLogger(__name__)


def merge_simulated_sms_into_payload(data: dict, captured: list[dict]) -> dict:
    """simulated_sms_list را به dict پاسخ JSON اضافه می‌کند (بدون تکرار id)."""
    if not captured:
        return data
    existing = data.get("simulated_sms_list")
    if not isinstance(existing, list):
        existing = []
    seen = {str(x.get("id")) for x in existing if isinstance(x, dict) and x.get("id")}
    merged = list(existing)
    for entry in captured:
        if not isinstance(entry, dict) or not entry.get("message"):
            continue
        eid = str(entry.get("id") or "")
        if eid and eid in seen:
            continue
        if eid:
            seen.add(eid)
        merged.append(entry)
    if not merged:
        return data
    out = dict(data)
    out["simulated_sms_list"] = merged
    if len(merged) == 1:
        out["simulated_sms"] = merged[0]
    elif not out.get("simulated_sms"):
        out["simulated_sms"] = merged[0]
    return out


class SmsSimulationCaptureMiddleware(BaseHTTPMiddleware):
    """هر POST/PATCH/PUT/DELETE روی /api/ — begin_capture؛ در پاسخ JSON لیست پاپ‌آپ را برمی‌گرداند."""

    async def dispatch(self, request: Request, call_next):
        path = request.scope.get("path") or request.url.path
        capture = (
            sms_sim.simulation_recording_enabled()
            and path.startswith("/api/")
            and request.method.upper() in ("POST", "PUT", "PATCH", "DELETE")
        )
        if capture:
            sms_sim.begin_capture()
        try:
            response = await call_next(request)
        except Exception:
            if capture:
                sms_sim.drain_capture()
            raise

        if not capture:
            return response

        captured = sms_sim.drain_capture()
        if not captured or response.status_code < 200 or response.status_code >= 300:
            return response

        ctype = (response.headers.get("content-type") or "").lower()
        if "application/json" not in ctype:
            return response

        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        if not isinstance(data, dict):
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        merged = merge_simulated_sms_into_payload(data, captured)
        if merged is data:
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
        return JSONResponse(content=merged, status_code=response.status_code, headers=headers)
