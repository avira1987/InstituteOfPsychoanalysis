"""FastAPI application entry point."""

import asyncio
import os
import uuid
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.database import init_db, async_session_factory
from app.services.sla_monitor import sla_monitor
from app.services.calendar_triggers import calendar_trigger_monitor

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


async def _maybe_auto_seed_demo_after_empty_db():
    """
    اگر SEED_DEMO_ON_STARTUP فعال باشد و هنوز هیچ دانشجویی در DB نیست،
    همان دیتابیسی که API به آن وصل است با دادهٔ دمو پر می‌شود (مشکل «پنل خالی» با Docker).
    """
    if not settings.SEED_DEMO_ON_STARTUP:
        return

    from sqlalchemy import func, select

    from app.models.operational_models import Student
    from app.demo_process_walker import seed_branch_scenarios, seed_full_matrix

    os.environ.setdefault("SMS_PROVIDER", "log")
    os.environ.setdefault("OTP_RESTRICT_TO_STUDENT_PHONES", "false")
    demo_pass = os.environ.get("DEMO_MATRIX_STUDENT_PASSWORD", "demo_student_123")

    async with async_session_factory() as db:
        total_students = (
            await db.execute(select(func.count()).select_from(Student))
        ).scalar() or 0
        if total_students > 0:
            logger.info(
                "Auto demo seed skipped: database already has %s student(s).",
                total_students,
            )
            return

    logger.info("SEED_DEMO_ON_STARTUP: seeding demo data into this database...")
    try:
        async with async_session_factory() as db:
            await seed_branch_scenarios(db, None, None, demo_pass)
        logger.info("Demo scenarios (DEMO-SCEN-*) seeded.")
    except Exception:
        logger.exception("Demo scenario seed failed")

    if settings.SEED_DEMO_FULL_MATRIX:

        async def _run_matrix():
            try:
                async with async_session_factory() as db2:
                    await seed_full_matrix(db2, None, None, demo_pass)
                logger.info("Full demo matrix (AUTO-DEMO-*) finished in background.")
            except Exception:
                logger.exception("Full demo matrix seed failed")

        asyncio.create_task(_run_matrix())
        logger.info("Full demo matrix started in background (may take a few minutes).")


async def _maybe_seed_demo_financial_if_empty():
    """
    اگر دانشجو در DB هست ولی جدول مالی خالی است، رکوردهای دمو را اضافه می‌کند
    (فقط وقتی SEED_DEMO_ON_STARTUP فعال است؛ برای دیتابیس‌های قدیمی بدون دادهٔ مالی).
    """
    if not settings.SEED_DEMO_ON_STARTUP:
        return
    from sqlalchemy import func, select

    from app.demo_financial_seed import ensure_demo_financial_records
    from app.models.operational_models import FinancialRecord, Student

    async with async_session_factory() as db:
        fc = (await db.execute(select(func.count(FinancialRecord.id)))).scalar() or 0
        if fc > 0:
            return
        sc = (await db.execute(select(func.count(Student.id)))).scalar() or 0
        if sc == 0:
            return
        n = await ensure_demo_financial_records(db)
        if n:
            logger.info("SEED_DEMO_ON_STARTUP: demo financial records added (%s rows).", n)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events."""
    logging.basicConfig(level=logging.INFO)
    # Startup
    await init_db()
    await _seed_if_empty()
    await _maybe_auto_seed_demo_after_empty_db()
    await _maybe_seed_demo_financial_if_empty()

    # BUILD_TODO § ج-۲ (بخش ۴): Start SLA monitoring loop in background
    interval = settings.SLA_CHECK_INTERVAL_SECONDS
    sla_task = asyncio.create_task(
        sla_monitor.start_monitoring_loop(async_session_factory, interval_seconds=interval)
    )
    app.state.sla_monitor_task = sla_task
    logger.info("SLA monitoring loop started (background)")

    cal_interval = settings.CALENDAR_TRIGGER_INTERVAL_SECONDS
    cal_task = asyncio.create_task(
        calendar_trigger_monitor.start_loop(async_session_factory, interval_seconds=cal_interval)
    )
    app.state.calendar_trigger_task = cal_task
    logger.info("Calendar trigger loop started (background)")

    yield

    # Shutdown: cancel background loops (otherwise asyncio.sleep(interval) blocks for minutes)
    sla_monitor.stop_monitoring()
    t_sla = getattr(app.state, "sla_monitor_task", None)
    if t_sla and not t_sla.done():
        t_sla.cancel()
        try:
            await t_sla
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug("SLA monitor task exit: %s", e)

    calendar_trigger_monitor.stop()
    t_cal = getattr(app.state, "calendar_trigger_task", None)
    if t_cal and not t_cal.done():
        t_cal.cancel()
        try:
            await t_cal
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug("Calendar trigger task exit: %s", e)


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
from app.api.blog_routes import router as blog_router
from app.api.public_routes import router as public_router
from app.api.therapy_routes import router as therapy_router
from app.api.finance_routes import router as finance_router
from app.api.assignment_routes import router as assignment_router

app.include_router(auth_router)
app.include_router(process_router)
app.include_router(student_router)
app.include_router(admin_router)
app.include_router(payment_router)
app.include_router(blog_router)
app.include_router(public_router)
app.include_router(therapy_router)
app.include_router(finance_router)
app.include_router(assignment_router)

# ─── Serve uploaded files (avatars) ─────────────────────────────
UPLOAD_DIR = Path(__file__).resolve().parent.parent / settings.UPLOAD_DIR
if UPLOAD_DIR.exists() or True:  # mount anyway so uploads can be created at runtime
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


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


# ─── Serve Admin UI (همان build با base=/anistito/؛ پشت Apache مسیر به /assets ستریپ می‌شود) ───
ADMIN_UI_DIR = Path(__file__).parent.parent / "admin-ui" / "dist"

if ADMIN_UI_DIR.exists():
    _assets = ADMIN_UI_DIR / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="static-assets")

    _index = ADMIN_UI_DIR / "index.html"

    @app.get("/")
    async def serve_spa_root():
        # پشت Apache معمولاً همین «/» است؛ دسترسی مستقیم /anistito/ هم با middleware به اینجا می‌رسد
        return FileResponse(str(_index))

    # فایل‌های استاتیک و مسیرهای SPA
    @app.get("/{filename}")
    async def serve_static_file(filename: str):
        # برای /api، اجازه بده خود FastAPI 404 JSON بدهد
        if filename == "api":
            raise StarletteHTTPException(status_code=404, detail="Not Found")
        file_path = ADMIN_UI_DIR / filename
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        # برای مسیرهای SPA (login و ...)، index.html را برگردان
        return FileResponse(str(_index))

    # fallback برای 404ها (به جز API)
    @app.exception_handler(404)
    async def spa_fallback(request, exc):
        if request.url.path.startswith("/api"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        return FileResponse(str(_index))
else:
    # اگر build فرانت موجود نباشد
    @app.get("/")
    async def root():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "running",
            "docs": "/docs",
            "note": "Admin UI is not built. Run: cd admin-ui && npm run build",
        }
