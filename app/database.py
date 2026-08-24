"""Database session management and Base model."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings
from app.observability.slow_sql import register_slow_sql_listener

settings = get_settings()

_engine_kwargs = {
    "echo": settings.DATABASE_ECHO,
    "pool_pre_ping": True,
    "pool_size": settings.DB_POOL_SIZE,
    "max_overflow": settings.DB_MAX_OVERFLOW,
    "pool_recycle": settings.DB_POOL_RECYCLE_SECONDS,
    "pool_timeout": settings.DB_POOL_TIMEOUT_SECONDS,
}

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)
register_slow_sql_listener(engine)


def db_pool_snapshot() -> dict | None:
    """SQLAlchemy pool counters for the admin observability panel."""
    try:
        pool = engine.sync_engine.pool
        return {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        }
    except Exception:
        return None


async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """Dependency that yields an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def apply_schema_safety_patches(conn) -> None:
    """Idempotent column/table fixes when Alembic stamp drifted ahead of real schema."""
    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(512)"))
    # '' collides with UNIQUE(email); admin create-user used to store empty string
    await conn.execute(text("UPDATE users SET email = NULL WHERE email = ''"))
    await conn.execute(text("UPDATE users SET phone = NULL WHERE phone = ''"))
    await conn.execute(
        text("ALTER TABLE ticket_comments ADD COLUMN IF NOT EXISTS kind VARCHAR(20) DEFAULT 'user'")
    )
    await conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS sms_simulation_outbox (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                phone VARCHAR(32) NOT NULL,
                message TEXT NOT NULL,
                kind VARCHAR(32) NOT NULL,
                template_key VARCHAR(120),
                created_at TIMESTAMPTZ NOT NULL
            )
            """
        )
    )
    await conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS sms_simulation_dismissals (
                sms_id VARCHAR(36) NOT NULL,
                user_id VARCHAR(36) NOT NULL,
                dismissed_at TIMESTAMPTZ NOT NULL,
                PRIMARY KEY (sms_id, user_id),
                FOREIGN KEY (sms_id) REFERENCES sms_simulation_outbox(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
    )
    await conn.execute(
        text("CREATE INDEX IF NOT EXISTS ix_sms_sim_outbox_phone ON sms_simulation_outbox (phone)")
    )
    await conn.execute(
        text("CREATE INDEX IF NOT EXISTS ix_sms_sim_outbox_created ON sms_simulation_outbox (created_at)")
    )
    await conn.execute(
        text("CREATE INDEX IF NOT EXISTS ix_sms_sim_dismiss_user ON sms_simulation_dismissals (user_id)")
    )
    await conn.execute(
        text("ALTER TABLE interview_slots ADD COLUMN IF NOT EXISTS host_meeting_link TEXT")
    )
    await conn.execute(
        text("ALTER TABLE interview_slots ADD COLUMN IF NOT EXISTS interviewer_meeting_link TEXT")
    )
    await conn.execute(
        text("ALTER TABLE therapy_sessions ADD COLUMN IF NOT EXISTS host_meeting_url TEXT")
    )
    await conn.execute(
        text(
            "ALTER TABLE interview_slots ADD COLUMN IF NOT EXISTS student_join_open BOOLEAN NOT NULL DEFAULT false"
        )
    )
    await conn.execute(
        text("ALTER TABLE term_course_offerings ADD COLUMN IF NOT EXISTS online_meeting_url TEXT")
    )
    await conn.execute(
        text("ALTER TABLE term_course_offerings ADD COLUMN IF NOT EXISTS host_meeting_url TEXT")
    )


async def init_db():
    """Create all tables (for development only; use Alembic in production)."""
    import asyncio
    import logging

    import app.models.dynamic_forms  # noqa: F401 — ثبت جداول روی Base
    import app.models.operational_models  # noqa: F401 — sms_simulation_outbox و …

    log = logging.getLogger(__name__)
    attempts = 8
    for attempt in range(attempts):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            break
        except Exception as e:
            if attempt >= attempts - 1:
                raise
            log.warning(
                "init_db: database connection failed (%s/%s): %s — retrying…",
                attempt + 1,
                attempts,
                e,
            )
            await asyncio.sleep(2)
    async with engine.begin() as conn:
        await apply_schema_safety_patches(conn)
