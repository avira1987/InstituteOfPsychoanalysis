# انیستیتو روانکاوری تهران | Tehran Institute of Psychoanalysis

Meta-Driven Educational Automation System for Tehran Institute of Psychoanalysis.

## Architecture

- **Backend**: FastAPI + SQLAlchemy (async) + PostgreSQL
- **Core Engine**: Metadata-driven State Machine with Rule Engine
- **Frontend**: React + Vite — داشبورد ادمین + **پورتال‌ها** (دانشجو، کارمند، درمانگر، سوپروایزر، مدیر سایت، …) در `admin-ui/src/pages/`
- **Background**: حلقهٔ **SLA** (`sla_monitor`) + حلقهٔ **تریگرهای تقویمی** (`calendar_triggers`) در `lifespan` اپ
- **Infrastructure**: Docker Compose + Redis + Alembic migrations

## Quick Start

### With Docker (Recommended)

```bash
docker-compose up --build
```

- API و Admin UI: http://localhost:3000 (یک پورت واحد)
- API Docs: http://localhost:3000/docs

### Without Docker

نیاز به **PostgreSQL** روی localhost (مثلاً با `docker compose up -d db` و پورت `5432`).

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up environment
cp .env.example .env
# DATABASE_URL باید به همان Postgres اشاره کند (پیش‌فرض در .env.example)

# 3. Run migrations
alembic upgrade head

# 4. Seed metadata
python -m app.meta.seed

# 5. Start server (پورت 3000 — یک پورت برای API و فرانت)
uvicorn app.main:app --reload --port 3000
```

## Project Structure

```
anistito/
├── app/
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Environment-based settings
│   ├── database.py             # Async SQLAlchemy setup
│   ├── core/                   # Core Engine (no hardcoded business logic)
│   │   ├── engine.py           # StateMachineEngine
│   │   ├── rule_engine.py      # RuleEvaluator
│   │   ├── transition.py       # TransitionManager
│   │   ├── event_bus.py        # EventBus
│   │   └── audit.py            # AuditLogger
│   ├── meta/                   # Metadata layer
│   │   ├── schemas.py          # Pydantic schemas
│   │   ├── seed.py             # Seed script
│   │   └── loader.py           # MetadataLoader
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── meta_models.py      # Process/State/Transition/Rule definitions
│   │   ├── operational_models.py  # Students/Instances/Sessions/Financials
│   │   └── audit_models.py     # Audit logs
│   ├── api/                    # REST API routes
│   │   ├── auth.py             # Authentication & RBAC
│   │   ├── auth_routes.py      # Auth endpoints
│   │   ├── admin/routes.py     # Admin CRUD endpoints
│   │   ├── process/routes.py   # Process execution endpoints
│   │   └── student/routes.py   # Student endpoints
│   └── services/               # Business services
│       ├── notification_service.py
│       ├── sla_monitor.py
│       ├── calendar_triggers.py  # تریگرهای زمان‌محور (مکمل SLA)
│       ├── payment_service.py
│       ├── attendance_service.py
│       ├── process_service.py
│       └── student_service.py
├── metadata/                   # JSON seed files
│   ├── processes/              # 7 SOP process definitions
│   ├── rules/                  # Rule definitions
│   └── roles.json              # Role definitions
├── tests/                      # Unit tests
├── admin-ui/                   # React Admin Dashboard
├── docker-compose.yml
├── Dockerfile
├── alembic.ini
└── requirements.txt
```

## SOP Processes (7 total)

| # | Process | Code |
|---|---------|------|
| 1 | مرخصی آموزشی موقت | `educational_leave` |
| 2 | آغاز درمان آموزشی | `start_therapy` |
| 3 | مدیریت تغییرات درمان آموزشی | `therapy_changes` |
| 4 | برگزاری جلسه اضافی | `extra_session` |
| 5 | پرداخت جلسات آتی | `session_payment` |
| 6 | حضور و غیاب | `attendance_tracking` |
| 7 | تعیین تکلیف هزینه جلسه | `fee_determination` |

## Key Design Principles

- **No hardcoded business logic**: All rules stored as JSON in `rule_definitions`
- **Rule changes without code changes**: Edit metadata in database only
- **Complete audit trail**: Every transition, rule change, and override logged
- **Role-based access control**: Each transition specifies required role
- **Versioning**: ProcessDefinition and RuleDefinition have version tracking

## API Endpoints

### Authentication
- `POST /api/auth/login` - Get access token
- `POST /api/auth/register` - Register user (admin only)
- `GET /api/auth/me` - Current user profile

### Process Execution
- `GET /api/process/definitions` - List process definitions
- `POST /api/process/start` - Start a new process instance
- `POST /api/process/{id}/trigger` - Execute a transition
- `GET /api/process/{id}/status` - Get instance status
- `GET /api/process/{id}/transitions` - Available transitions

### Admin CRUD
- `GET/POST /api/admin/processes` - Process CRUD
- `GET/POST /api/admin/processes/{id}/states` - State CRUD
- `GET/POST /api/admin/processes/{id}/transitions` - Transition CRUD
- `GET/POST /api/admin/rules` - Rule CRUD
- `GET /api/admin/audit-logs` - Audit log viewer
- `GET /api/admin/dashboard/stats` - Dashboard statistics

## Running Tests

```bash
pip install -r requirements.txt
pytest -v
```
