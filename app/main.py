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
from starlette.middleware.gzip import GZipMiddleware

from app.config import get_settings
from app.database import init_db, async_session_factory, apply_schema_safety_patches, engine
from app.services.sla_monitor import sla_monitor
from app.services.calendar_triggers import calendar_trigger_monitor

settings = get_settings()
logger = logging.getLogger(__name__)

# ثبت مدل‌های فرم داینامیک روی metadata (بدون وابستگی چرخه‌ای با operational_models)
import app.models.dynamic_forms  # noqa: F401


async def _ensure_admin_user(db):
    """Ensure admin user exists. Password reset to admin123 only in DEBUG mode."""
    from sqlalchemy import select
    from app.models.operational_models import User
    from app.api.auth import get_password_hash, verify_password

    result = await db.execute(select(User).where(User.username == "admin"))
    admin = result.scalars().first()
    if admin:
        if settings.DEBUG:
            try:
                ok = admin.hashed_password and verify_password("admin123", admin.hashed_password)
            except Exception:
                ok = False
            if not ok:
                admin.hashed_password = get_password_hash("admin123")
                admin.is_active = True
                await db.commit()
                logger.warning("DEBUG: admin password reset to admin123")
        return
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
    if settings.DEBUG:
        logger.warning("DEBUG: default admin created (username=admin, password=admin123)")
    else:
        logger.warning("Default admin user created — set password immediately via secure channel")


async def _ensure_system_actor_user(db):
    """کاربر سیستمی (SYSTEM_ACTOR_ID) که started_by/state_history و سرویس‌های تقویم به آن ارجاع می‌دهند."""
    import uuid
    from app.models.operational_models import User
    from app.api.auth import get_password_hash

    system_actor_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    existing = await db.get(User, system_actor_id)
    if existing is None:
        db.add(
            User(
                id=system_actor_id,
                username="system_actor",
                email="system_actor@local",
                hashed_password=get_password_hash("unused"),
                full_name_fa="سیستم",
                role="admin",
            )
        )
        await db.commit()
        logger.debug("System actor user created: id=%s", system_actor_id)


async def _seed_if_empty():
    """Seed metadata and create default admin user if DB is empty."""
    from sqlalchemy import select, func
    from app.models.meta_models import ProcessDefinition
    from app.models.operational_models import User
    from app.api.auth import get_password_hash

    async with async_session_factory() as db:
        # Always ensure admin user exists (create or fix password)
        await _ensure_admin_user(db)
        # Always ensure the system actor user exists (FK target for system-initiated processes)
        await _ensure_system_actor_user(db)
        from app.services.institute_operational_anchor import ensure_institute_operational_student

        await ensure_institute_operational_student(db)
        await db.commit()

        # Check if process definitions exist
        result = await db.execute(select(func.count(ProcessDefinition.id)))
        count = result.scalar()
        if count > 0:
            logger.debug("Database already has %s processes, skipping metadata seed.", count)
            return

        # Seed metadata
        logger.debug("Empty database detected. Seeding metadata...")
        from app.meta.seed import load_rules, load_process, METADATA_DIR
        await load_rules(db)

        processes_dir = METADATA_DIR / "processes"
        if processes_dir.exists():
            for pf in sorted(processes_dir.glob("*.json")):
                await load_process(db, pf)

        await db.commit()
        logger.debug("Metadata seed completed.")


async def _maybe_auto_seed_demo_after_empty_db():
    """
    اگر SEED_DEMO_ON_STARTUP فعال باشد و هنوز هیچ دانشجویی در DB نیست،
    همان دیتابیسی که API به آن وصل است با دادهٔ دمو پر می‌شود (مشکل «پنل خالی» با Docker).
    """
    if not settings.SEED_DEMO_ON_STARTUP:
        return

    from sqlalchemy import func, select

    from app.models.operational_models import Student
    from app.demo_process_walker import seed_branch_scenarios, seed_full_matrix, seed_profile_state_students

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
            await seed_profile_state_students(db, demo_pass)
        logger.info("Demo scenarios (DEMO-SCEN-*) and profile matrix (AUTO-PROFILE-*) seeded.")
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
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    # Startup
    from app.core.production_guards import validate_production_settings

    validate_production_settings(settings)
    if settings.INIT_DB_ON_STARTUP and settings.DEBUG:
        await init_db()
    elif settings.INIT_DB_ON_STARTUP and not settings.DEBUG:
        logger.info("INIT_DB_ON_STARTUP skipped in production — use Alembic migrations only")
    else:
        # Docker / production: Alembic owns DDL; apply only idempotent safety patches.
        try:
            async with engine.begin() as conn:
                await apply_schema_safety_patches(conn)
        except Exception as e:
            logger.warning("schema safety patches skipped (DB not ready yet): %s", e)
    from app.services import sms_simulation_service as sms_sim

    if sms_sim.simulation_recording_enabled():
        logger.info(
            "SMS simulation ON — popups active (SMS_PROVIDER=log, SMS_SIMULATION_UI=true)"
        )
    else:
        logger.info(
            "SMS simulation OFF — no dev popups (SMS_PROVIDER=%s, SMS_SIMULATION_UI=%s)",
            settings.SMS_PROVIDER,
            getattr(settings, "SMS_SIMULATION_UI", False),
        )
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

    from app.services.notification_outbox_service import notification_outbox_worker

    outbox_task = asyncio.create_task(
        notification_outbox_worker.start_loop(async_session_factory, interval_seconds=60)
    )
    app.state.notification_outbox_task = outbox_task
    logger.info("Notification outbox worker started (background)")

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

    from app.services.notification_outbox_service import notification_outbox_worker

    notification_outbox_worker.stop()
    t_out = getattr(app.state, "notification_outbox_task", None)
    if t_out and not t_out.done():
        t_out.cancel()
        try:
            await t_out
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug("Notification outbox task exit: %s", e)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="سیستم اتوماسیون آموزشی متادیتا-محور - Meta-Driven Educational Automation System",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

# Strip /anistito prefix when behind Apache proxy (ProxyPass /anistito -> backend)
from starlette.middleware.base import BaseHTTPMiddleware

from app.middleware.sms_simulation_capture import SmsSimulationCaptureMiddleware
from app.middleware.login_rate_limit import LoginRateLimitMiddleware
from app.middleware.uploads_auth import UploadsAuthMiddleware

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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """هدرهای حداقلی امنیتی برای پاسخ‌های API و SPA (مکمل Apache)."""
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=()",
        )
        return response


def _cors_origins_and_credentials():
    raw = (get_settings().CORS_ALLOW_ORIGINS or "").strip()
    if raw == "*" or not raw:
        return ["*"], False
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return (parts if parts else ["*"]), True


_origins, _cors_cred = _cors_origins_and_credentials()

# ترتیب: اولین add = بیرونی‌ترین؛ مسیر /anistito باید قبل از CORS و هدرها اصلاح شود.
app.add_middleware(StripPathPrefixMiddleware)
app.add_middleware(LoginRateLimitMiddleware)
app.add_middleware(UploadsAuthMiddleware)
app.add_middleware(SmsSimulationCaptureMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_cors_cred,
    allow_methods=["*"],
    allow_headers=["*"],
)
# بیرونی‌ترین لایه: فشرده‌سازی پاسخ (JS/CSS/HTML بزرگ — سبک‌تر روی شبکهٔ اینترنت)
app.add_middleware(GZipMiddleware, minimum_size=800, compresslevel=6)

# ─── Register Routers ──────────────────────────────────────────

from app.api.process.routes import router as process_router
from app.api.student.routes import router as student_router
from app.api.admin.routes import router as admin_router
from app.api.auth_routes import router as auth_router
from app.api.payment_routes import router as payment_router
from app.api.blog_routes import router as blog_router
from app.api.public_routes import router as public_router
from app.api.therapy_routes import router as therapy_router
from app.api.therapy_workbench_routes import router as therapy_workbench_router
from app.api.finance_routes import router as finance_router
from app.api.assignment_routes import router as assignment_router
from app.api.ticket_routes import router as ticket_router
from app.api.reports_routes import router as reports_router
from app.api.panel_routes import router as panel_router
from app.api.interview_slots_routes import router as interview_slots_router
from app.api.educational_therapist_slots_routes import router as educational_therapist_slots_router
from app.api.alocom_routes import router as alocom_router
from app.api.dynamic_form_routes import router as dynamic_forms_router, nav_router as portal_nav_dynamic_router
from app.flow_through.routes import router as flow_through_router

app.include_router(auth_router)
app.include_router(process_router)
app.include_router(student_router)
app.include_router(admin_router)
app.include_router(payment_router)
app.include_router(blog_router)
app.include_router(public_router)
app.include_router(therapy_router)
app.include_router(therapy_workbench_router)
app.include_router(finance_router)
app.include_router(assignment_router)
app.include_router(ticket_router)
app.include_router(reports_router)
app.include_router(panel_router)
app.include_router(dynamic_forms_router)
app.include_router(portal_nav_dynamic_router)
app.include_router(interview_slots_router)
app.include_router(educational_therapist_slots_router)
app.include_router(alocom_router)
app.include_router(flow_through_router)

# ─── Serve uploaded files (avatars) ─────────────────────────────
UPLOAD_DIR = Path(__file__).resolve().parent.parent / settings.UPLOAD_DIR
if UPLOAD_DIR.exists() or True:  # mount anyway so uploads can be created at runtime
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


@app.get("/health")
async def health_liveness():
    return {"status": "healthy", "version": settings.APP_VERSION}


@app.get("/health/ready")
async def health_readiness():
    """Readiness: DB ping + optional migration head check."""
    from sqlalchemy import text
    from app.database import async_session_factory

    try:
        async with async_session_factory() as db:
            await db.execute(text("SELECT 1"))
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "db": False, "error": str(e)[:200]},
        )
    return {"status": "healthy", "db": True, "version": settings.APP_VERSION}


@app.get("/debug/process-count")
async def debug_process_count():
    """Debug: return process count (no auth) — فقط وقتی DEBUG=true."""
    if not settings.DEBUG:
        raise StarletteHTTPException(status_code=404, detail="Not Found")
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
        # بیلد Vite با base=/anistito/ — بدون Apache، مستقیم به همین مسیر هم سرو شود
        app.mount("/anistito/assets", StaticFiles(directory=str(_assets)), name="static-assets-anistito")

    _index = ADMIN_UI_DIR / "index.html"

    def _spa_index_response():
        response = FileResponse(str(_index))
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response

    def _is_static_asset_path(path: str) -> bool:
        if "/assets/" in path:
            return True
        return path.endswith((".js", ".css", ".woff2", ".woff", ".png", ".ico", ".svg", ".map"))

    @app.get("/")
    async def serve_spa_root():
        # پشت Apache معمولاً همین «/» است؛ دسترسی مستقیم /anistito/ هم با middleware به اینجا می‌رسد
        return _spa_index_response()

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
        return _spa_index_response()

    # fallback برای 404ها (به جز API و فایل‌های استاتیک بیلد)
    @app.exception_handler(404)
    async def spa_fallback(request, exc):
        path = request.url.path
        if path.startswith("/api") or _is_static_asset_path(path):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        return _spa_index_response()
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
