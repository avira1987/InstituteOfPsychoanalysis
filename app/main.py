"""FastAPI application entry point."""

import uuid
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import init_db, async_session_factory

settings = get_settings()
logger = logging.getLogger(__name__)


async def _ensure_admin_user(db):
    """Ensure admin user exists with correct password (admin/admin123)."""
    from sqlalchemy import select
    from app.models.operational_models import User
    from app.api.auth import get_password_hash, verify_password

    result = await db.execute(select(User).where(User.username == "admin"))
    admin = result.scalars().first()
    if admin:
        # Admin exists - verify password works; if not, reset to admin123
        try:
            ok = admin.hashed_password and verify_password("admin123", admin.hashed_password)
        except Exception:
            ok = False
        if not ok:
            admin.hashed_password = get_password_hash("admin123")
            admin.is_active = True
            await db.commit()
            logger.info("Admin password reset to admin123 (previous hash was invalid)")
    else:
        admin = User(
            id=uuid.uuid4(),
            username="admin",
            email="admin@anistito.ir",
            hashed_password=get_password_hash("admin123"),
            full_name_fa="مدیر سیستم",
            role="admin",
        )
        db.add(admin)
        await db.commit()
        logger.info("Default admin created: username=admin, password=admin123")


async def _seed_if_empty():
    """Seed metadata and create default admin user if DB is empty."""
    from sqlalchemy import select, func
    from app.models.meta_models import ProcessDefinition
    from app.models.operational_models import User
    from app.api.auth import get_password_hash

    async with async_session_factory() as db:
        # Always ensure admin user exists (create or fix password)
        await _ensure_admin_user(db)

        # Check if process definitions exist
        result = await db.execute(select(func.count(ProcessDefinition.id)))
        count = result.scalar()
        if count > 0:
            logger.info(f"Database already has {count} processes, skipping metadata seed.")
            return

        # Seed metadata
        logger.info("Empty database detected. Seeding metadata...")
        from app.meta.seed import load_rules, load_process, METADATA_DIR
        await load_rules(db)

        processes_dir = METADATA_DIR / "processes"
        if processes_dir.exists():
            for pf in sorted(processes_dir.glob("*.json")):
                await load_process(db, pf)

        await db.commit()
        logger.info("Metadata seed completed.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events."""
    logging.basicConfig(level=logging.INFO)
    # Startup
    await init_db()
    await _seed_if_empty()
    yield
    # Shutdown


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="سیستم اتوماسیون آموزشی متادیتا-محور - Meta-Driven Educational Automation System",
    lifespan=lifespan,
)

# Strip /anistito prefix when behind Apache proxy (ProxyPass /anistito -> backend)
from starlette.middleware.base import BaseHTTPMiddleware

class StripPathPrefixMiddleware(BaseHTTPMiddleware):
    """Strip /anistito prefix and normalize trailing slashes to avoid 307 redirects behind proxy."""
    async def dispatch(self, request, call_next):
        path = request.scope.get("path", "")
        if path.startswith("/anistito"):
            path = path[9:] or "/"  # strip /anistito (9 chars)
        # Normalize trailing slash for API routes (prevents 307 redirect -> wrong Location behind proxy)
        if path.startswith("/api/") and path != "/" and path.endswith("/"):
            path = path.rstrip("/")
        request.scope["path"] = path
        return await call_next(request)

app.add_middleware(StripPathPrefixMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Register Routers ──────────────────────────────────────────

from app.api.process.routes import router as process_router
from app.api.student.routes import router as student_router
from app.api.admin.routes import router as admin_router
from app.api.auth_routes import router as auth_router
from app.api.payment_routes import router as payment_router

app.include_router(auth_router)
app.include_router(process_router)
app.include_router(student_router)
app.include_router(admin_router)
app.include_router(payment_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/debug/process-count")
async def debug_process_count():
    """Debug: return process count (no auth) - remove in production."""
    from sqlalchemy import select, func
    from app.models.meta_models import ProcessDefinition
    from app.database import async_session_factory
    async with async_session_factory() as db:
        r = await db.execute(select(func.count(ProcessDefinition.id)))
        count = r.scalar()
    return {"process_count": count}


# ─── Serve Admin UI Static Files ────────────────────────────────
ADMIN_UI_DIR = Path(__file__).parent.parent / "admin-ui" / "dist"

if ADMIN_UI_DIR.exists():
    # Serve static assets (JS, CSS, etc.) - /anistito/assets/* becomes /assets/* after middleware
    app.mount("/assets", StaticFiles(directory=str(ADMIN_UI_DIR / "assets")), name="static-assets")

    # SPA root - when path is / (e.g. after /anistito/ stripped) or /
    @app.get("/")
    async def serve_spa_root():
        return FileResponse(str(ADMIN_UI_DIR / "index.html"))

    # Serve known static files from dist (e.g. vite.svg, favicon)
    @app.get("/{filename}")
    async def serve_static_file(filename: str):
        file_path = ADMIN_UI_DIR / filename
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        # For SPA client-side routes (login, processes, etc.), serve index.html
        return FileResponse(str(ADMIN_UI_DIR / "index.html"))

    # SPA fallback for nested client-side routes (e.g. /processes/123)
    @app.exception_handler(404)
    async def spa_fallback(request, exc):
        # API routes should return proper 404 JSON
        if request.url.path.startswith("/api/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        # Non-API 404s serve SPA index.html for client-side routing
        return FileResponse(str(ADMIN_UI_DIR / "index.html"))
else:
    @app.get("/")
    async def root():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "running",
            "docs": "/docs",
            "note": "Admin UI not built. Run 'npm run build' in admin-ui/ folder.",
        }
