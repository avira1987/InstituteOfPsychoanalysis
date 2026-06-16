"""Protect sensitive upload paths; avatars remain public."""

from __future__ import annotations

from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import FileResponse, JSONResponse, Response

from app.config import get_settings

# Public under /uploads (no auth required)
_PUBLIC_PREFIXES = ("/uploads/avatars/",)


def _is_protected_upload(path: str) -> bool:
    if not path.startswith("/uploads/"):
        return False
    for prefix in _PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return False
    return True


def _auth_error(detail: str, status_code: int = 401) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


class UploadsAuthMiddleware(BaseHTTPMiddleware):
    """Require Bearer token for process/dynamic-form uploads; serve file if authorized."""

    async def dispatch(self, request, call_next):
        path = request.scope.get("path", "")
        if request.method != "GET" or not _is_protected_upload(path):
            return await call_next(request)

        auth = request.headers.get("authorization") or ""
        if not auth.lower().startswith("bearer "):
            return _auth_error("Authentication required for this file")

        token = auth[7:].strip()
        if not token:
            return _auth_error("Authentication required for this file")

        from jose import JWTError, jwt
        from sqlalchemy import select

        from app.api.auth import ALGORITHM
        from app.config import get_settings
        from app.database import async_session_factory
        from app.models.operational_models import User

        settings = get_settings()
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("sub")
        except JWTError:
            return _auth_error("Invalid token")

        if not user_id:
            return _auth_error("Invalid token")

        async with async_session_factory() as db:
            import uuid

            try:
                uid = uuid.UUID(str(user_id))
            except ValueError:
                return _auth_error("Invalid token")
            r = await db.execute(select(User).where(User.id == uid, User.is_active.is_(True)))
            user = r.scalars().first()
            if not user:
                return _auth_error("User not found or inactive")

        upload_root = Path(settings.UPLOAD_DIR).resolve()
        rel = path[len("/uploads/") :]
        file_path = (upload_root / rel).resolve()
        if not str(file_path).startswith(str(upload_root)):
            return _auth_error("Invalid path", status_code=403)
        if not file_path.is_file():
            return await call_next(request)
        return FileResponse(str(file_path))
