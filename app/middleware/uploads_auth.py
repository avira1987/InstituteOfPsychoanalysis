"""Protect sensitive upload paths; avatars remain public."""

from __future__ import annotations

import uuid
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import FileResponse, JSONResponse

from app.core.user_roles import user_has_any_role, user_has_role

# Public under /uploads (no auth required)
_PUBLIC_PREFIXES = ("/uploads/avatars/",)

_OPERATOR_ROLES = (
    "admin",
    "staff",
    "finance",
    "deputy_education",
    "site_manager",
    "committee",
    "supervisor",
    "therapist",
    "interviewer",
    "instructor",
    "ta",
    "faculty_1",
    "educational_instructor",
)


def _is_protected_upload(path: str) -> bool:
    if not path.startswith("/uploads/"):
        return False
    for prefix in _PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return False
    return True


def _auth_error(detail: str, status_code: int = 401) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


def _extract_bearer(request) -> str | None:
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return token
    return None


async def _user_may_read_upload(db, user, path: str) -> bool:
    """Operators may read any protected file; students only their process/form instance folders."""
    if user_has_any_role(user, _OPERATOR_ROLES, admin_bypass=True):
        return True
    if not user_has_role(user, "student", admin_bypass=False):
        return False

    from sqlalchemy import select

    from app.models.operational_models import ProcessInstance, Student

    rel = path[len("/uploads/") :]
    parts = rel.split("/")
    instance_id: uuid.UUID | None = None
    if len(parts) >= 2 and parts[0] == "process_instances":
        try:
            instance_id = uuid.UUID(parts[1])
        except ValueError:
            return False
    elif len(parts) >= 2 and parts[0] == "dynamic_forms" and parts[1] != "standalone":
        try:
            instance_id = uuid.UUID(parts[1])
        except ValueError:
            return False
    else:
        return False

    st = (
        await db.execute(select(Student).where(Student.user_id == user.id))
    ).scalars().first()
    if not st:
        return False
    inst = (
        await db.execute(select(ProcessInstance).where(ProcessInstance.id == instance_id))
    ).scalars().first()
    return bool(inst and inst.student_id == st.id)


class UploadsAuthMiddleware(BaseHTTPMiddleware):
    """Require auth for process/dynamic-form uploads; serve file if authorized.

    Accepts Authorization Bearer JWT, or short-lived signed query (?exp=&sig=&uid=).
    Long-lived access_token query params are rejected.
    """

    async def dispatch(self, request, call_next):
        path = request.scope.get("path", "")
        if request.method != "GET" or not _is_protected_upload(path):
            return await call_next(request)

        # Reject legacy long-lived JWT-in-query
        if request.query_params.get("access_token") or (
            request.query_params.get("token") and not request.query_params.get("sig")
        ):
            return _auth_error("Use a short-lived signed URL or Authorization header", status_code=401)

        from jose import JWTError, jwt
        from sqlalchemy import select

        from app.config import get_settings
        from app.database import async_session_factory
        from app.models.operational_models import User
        from app.services.upload_signing import verify_upload_signature

        settings = get_settings()
        user = None

        bearer = _extract_bearer(request)
        if bearer:
            try:
                payload = jwt.decode(bearer, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                user_id = payload.get("sub")
            except JWTError:
                return _auth_error("Invalid token")
            if not user_id:
                return _auth_error("Invalid token")
            async with async_session_factory() as db:
                try:
                    uid = uuid.UUID(str(user_id))
                except ValueError:
                    return _auth_error("Invalid token")
                r = await db.execute(select(User).where(User.id == uid, User.is_active.is_(True)))
                user = r.scalars().first()
                if not user:
                    return _auth_error("User not found or inactive")
                if not await _user_may_read_upload(db, user, path):
                    return _auth_error("Forbidden", status_code=403)
        else:
            exp = request.query_params.get("exp")
            sig = request.query_params.get("sig")
            uid_q = (request.query_params.get("uid") or "").strip()
            if not verify_upload_signature(path, exp, sig, user_id=uid_q):
                return _auth_error("Authentication required for this file")
            if not uid_q:
                return _auth_error("Authentication required for this file")
            async with async_session_factory() as db:
                try:
                    uid = uuid.UUID(uid_q)
                except ValueError:
                    return _auth_error("Invalid token")
                r = await db.execute(select(User).where(User.id == uid, User.is_active.is_(True)))
                user = r.scalars().first()
                if not user:
                    return _auth_error("User not found or inactive")
                if not await _user_may_read_upload(db, user, path):
                    return _auth_error("Forbidden", status_code=403)

        upload_root = Path(settings.UPLOAD_DIR).resolve()
        rel = path[len("/uploads/") :]
        file_path = (upload_root / rel).resolve()
        if not str(file_path).startswith(str(upload_root)):
            return _auth_error("Invalid path", status_code=403)
        if not file_path.is_file():
            return await call_next(request)
        return FileResponse(str(file_path))
