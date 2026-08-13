"""Application configuration loaded from environment variables."""

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# مسیر بارگذاری .env برای pydantic-settings (SMS، درگاه پرداخت، DB، …):
# - پیش‌فرض: `<ریشهٔ مخزن>/.env`
# - جایگزین: متغیر محیطی ANISTITO_ENV_FILE (مسیر مطلق یا نسبت به cwd هنگام استارت)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_env_override = (os.environ.get("ANISTITO_ENV_FILE") or "").strip()
if _env_override:
    ENV_FILE_PATH = Path(_env_override).expanduser().resolve()
else:
    ENV_FILE_PATH = _PROJECT_ROOT / ".env"

PROJECT_ROOT = _PROJECT_ROOT
_ENV_FILE_FOR_SETTINGS = ENV_FILE_PATH if ENV_FILE_PATH.is_file() else None


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Tehran Institute of Psychoanalysis - انستیتو روانکاوری تهران"
    APP_VERSION: str = "1.0.0"
    # لوکال: در .env مقدار true بگذارید. برای استقرار اینترنتی حتماً false.
    DEBUG: bool = False
    # اگر false باشد در استارت API فقط Alembic اسکیما را مدیریت می‌کند (بدون create_all)
    INIT_DB_ON_STARTUP: bool = True
    APP_BASE_URL: str = "https://lms.psychoanalysis.ir/anistito"  # ریدایرکت بعد از کال‌بک پرداخت، لینک SMS، …
    # فقط وقتی ادمین وجود ندارد: رمز اولیه از env (حداقل ۸ کاراکتر). در DEBUG بدون این مقدار از admin123 استفاده می‌شود.
    INITIAL_ADMIN_PASSWORD: str = ""
    # seed دمو / flow-through — در production باید false باشد
    ALLOW_DEMO_SEED: bool = False
    FLOW_THROUGH_SEED_ENABLED: bool = False
    # مسیر نسب به APP_BASE_URL؛ پس از بازگشت از درگاه به این صفحه هدایت می‌شود
    PAYMENT_RETURN_PATH: str = "/panel/portal/student"

    # Database (PostgreSQL only — همان مقدار در Docker: سرویس db)
    DATABASE_URL: str = "postgresql+asyncpg://anistito:anistito@localhost:5432/anistito"
    DATABASE_URL_SYNC: str = "postgresql://anistito:anistito@localhost:5432/anistito"
    DATABASE_ECHO: bool = False
    # روی VPSهای کوچک (۲ گیگ RAM) مقادیر کم‌تر؛ هر اتصال PG حافظه می‌گیرد و رشد بی‌حد cache در همان hostها OOM می‌دهد.
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE_SECONDS: int = 1800
    DB_POOL_TIMEOUT_SECONDS: int = 30

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth / JWT
    SECRET_KEY: str = "change-me-in-production-use-a-real-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    LOGIN_RATE_LIMIT_COUNT: int = 10
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 600

    # SMS — مقادیر از ENV_FILE_PATH (پیش‌فرض `.env` ریشهٔ مخزن) یا متغیرهای محیطی سیستم / Docker
    SMS_PROVIDER: str = "log"  # "log" | "mellipayamak"
    # وقتی SMS_PROVIDER=log؛ ذخیرهٔ متن در DB و polling پنل برای پاپ‌آپ تست (با mellipayamak بی‌اثر)
    # پیش‌فرض خاموش — برای تست لوکال در .env یا conftest روشن کنید
    SMS_SIMULATION_UI: bool = False
    # پاپ‌آپ «همه پیامک‌های شبیه‌سازی‌شده به هر گیرنده» برای نقش‌های غیردانشجو (طبق POPUP_WATCHER_ROLES)، قابل خاموش با false
    SMS_SIMULATION_POPUP_SHOW_ALL: bool = False
    # خالی = تمام نقش‌ها به جز student؛ یا admin,staff,finance
    SMS_SIMULATION_POPUP_WATCHER_ROLES: str = ""
    # با SMS_PROVIDER=mellipayamak هم متن را در outbox بگذار تا پاپ‌آپ تست همان لحظه/پولینگ کار کند
    SMS_SIMULATION_MIRROR_REAL_SEND: bool = False
    SMS_API_KEY: str = ""
    # Melipayamak: rest.payamak-panel.com با SMS_USERNAME (نام کاربری پنل، اغلب موبایل ۱۰ رقمی مثل 9032054361)
    # + SMS_PASSWORD یا همان APIKey پنل در SMS_API_KEY به‌جای password؛ فقط SMS_API_KEY بدون username → console.melipayamak.com
    SMS_USERNAME: str = ""
    SMS_PASSWORD: str = ""  # رمز وب‌سرویس پنل؛ اگر خالی باشد sms_gateway از SMS_API_KEY به‌عنوان password استفاده می‌کند
    SMS_LINE_NUMBER: str = ""  # شماره خط برای mellipayamak (مثال: 3000xxxx)
    # خط خدماتی اشتراکی — پیامک پترن (SendByBaseNumber2 / REST BaseServiceNumber)، مستند ملی‌پیامک
    # https://www.melipayamak.com/api/sendbybasenumber2/ — نگاشت قالب‌ها: metadata/sms_template_pattern_map.json
    SMS_PATTERN_BODY_ID: int = 0  # legacy؛ دیگر در مسیر ارسال متن آزاد استفاده نمی‌شود
    # کد پترن «کد ورود» در پنل؛ 0 = فقط SendOtp رسمی. پیش‌فرض: همان پترن تأییدشده در melipayamak_patterns.json
    SMS_OTP_PATTERN_BODY_ID: int = 449667

    # ورود با پیامک (دانشجو) — کد OTP فقط برای مسیر /api/auth/otp/*
    # در production (DEBUG=false) production_guards اجبار می‌کند true باشد مگر ALLOW_PUBLIC_OTP_SIGNUP=true.
    OTP_RESTRICT_TO_STUDENT_PHONES: bool = True
    # اگر true باشد حتی در DEBUG=false، OTP می‌تواند حساب دانشجو برای شمارهٔ ناشناس بسازد (عمداً باز کردن ثبت‌نام عمومی).
    ALLOW_PUBLIC_OTP_SIGNUP: bool = False
    # اگر true باشد، پاسخ request OTP فیلدهای dev_code/dev_hint می‌گیرد — در production معمولاً false.
    OTP_SHOW_CODE_IN_UI: bool = False
    # پس از اولین ورود موفق دانشجو با OTP: تولید رمز ساده، ذخیره در portal_password_plain و ارسال پیامک خوش‌آمد
    # ارسال واقعی با پترن ملی‌پیامک bodyId=450373 و کلید student_portal_welcome_credentials در metadata/sms_template_pattern_map.json
    STUDENT_FIRST_LOGIN_WELCOME_SMS: bool = True

    # Email
    EMAIL_SMTP_HOST: str = ""
    EMAIL_SMTP_PORT: int = 587
    EMAIL_FROM: str = "noreply@anistito.ir"

    # Payment (مبلغ API پرداخت به ریال برای سپ/زیبال/زرین‌پال؛ دفتر کل داخلی به تومان)
    PAYMENT_PROVIDER: str = "mock"  # "mock" | "saman" | "zibal" | "zarinpal"
    PAYMENT_CALLBACK_URL: str = "http://localhost:3000/api/payment/callback"
    # اگر True: فقط درگاه زیبال (و mock برای توسعه) — سپ/زرین‌پال در API غیرفعال
    PAYMENT_ZIBAL_ONLY: bool = True
    # حالت تست: اگر True، اتصال به درگاه واقعی به‌طور موقت غیرفعال می‌شود و پرداخت
    # بلافاصله «موفق» فرض شده تا کل جریان فرایند در سامانه قابل تست باشد.
    # هیچ کدِ درگاهی حذف نمی‌شود؛ برای بازگرداندن درگاه واقعی فقط این مقدار را False کنید
    # (یا متغیر محیطی PAYMENT_TEST_BYPASS را بردارید).
    PAYMENT_TEST_BYPASS: bool = False

    # Saman (SEP) Payment Gateway
    SEP_TERMINAL_ID: str = ""
    SEP_PASSWORD: str = ""

    # Zibal Payment Gateway
    ZIBAL_MERCHANT: str = ""
    ZIBAL_SANDBOX: bool = True  # use sandbox.zibal.ir for testing

    # Zarinpal Payment Gateway (REST v4 — merchant_id در پنل زرین‌پال)
    ZARINPAL_MERCHANT_ID: str = ""
    ZARINPAL_SANDBOX: bool = False  # True → sandbox.zarinpal.com

    # SLA Monitoring
    SLA_CHECK_INTERVAL_SECONDS: int = 300

    # Calendar / time-based triggers (payment_timeout, leave reminders, session_time_reached, …)
    CALENDAR_TRIGGERS_ENABLED: bool = True
    CALENDAR_TRIGGER_INTERVAL_SECONDS: int = 300

    # موتور چک روزانه کارهای عقب‌افتاده — SMS + نوتیفیکیشن پنل
    DAILY_OVERDUE_CHECK_ENABLED: bool = True
    DAILY_OVERDUE_CHECK_LOCAL_HOUR: int = 8
    DAILY_OVERDUE_CHECK_TZ: str = "Asia/Tehran"

    # پروندهٔ عملیاتی انستیتو برای فرایندهای نهادی (آماده‌سازی ترم)
    INSTITUTE_OPERATIONAL_STUDENT_CODE: str = "INST-OPS"
    # شروع خودکار آماده‌سازی زمستان N روز قبل از winter_start_date (از context پاییز)
    WINTER_PREP_AUTO_START_DAYS_BEFORE: int = 30

    # اسلات خودکار از الگوی هفتگی مصاحبه‌گر — حداکثر روز پیش‌نگر در هر Rule
    INTERVIEW_RECURRING_MAX_HORIZON_DAYS: int = 60

    # یادآوری پیامکی مصاحبهٔ پذیرش — چند ساعت قبل از شروع اسلات رزروشده
    INTERVIEW_REMINDER_HOURS_BEFORE: float = 2.0
    # چند دقیقه قبل از شروع مصاحبه که لینک آنلاین برای دانشجو/مصاحبه‌گر قابل مشاهده شود
    INTERVIEW_ONLINE_LINK_VISIBLE_MINUTES_BEFORE: int = 30

    # یادآوری پرداخت جلسات درمان — چند ساعت قبل از پایان مهلت SLA (awaiting_payment)
    SESSION_PAYMENT_REMINDER_HOURS_BEFORE_DEADLINE: float = 24.0

    # یادآوری پیامکی لینک جلسهٔ درمان آنلاین (الوکام) — چند دقیقه قبل از شروع جلسه
    THERAPY_SESSION_LINK_REMINDER_MINUTES_BEFORE: int = 30

    # مرخصی آموزشی: زمان‌بندی یادآوری بازگشت و مهلت ثبت‌نام (پس از فعال‌سازی وقفه در فرایند)
    EDUCATIONAL_LEAVE_RETURN_REMINDER_OFFSET_DAYS: int = 90
    EDUCATIONAL_LEAVE_RETURN_DEADLINE_AFTER_REMINDER_DAYS: int = 30

    # Uploads (avatars, etc.)
    UPLOAD_DIR: str = "uploads"  # مسیر نسبی از روت پروژه
    # فهرست بکاپ‌های روزانه روی دیسک (در prod: bind-mount /var/backups/anistito → /backups)
    BACKUP_DIR: str = "backups"

    # Optional outbound integration (LMS / سامانه بیرونی) — اکشن‌های «ثبت در LMS»
    LMS_INTEGRATION_WEBHOOK_URL: str = ""  # اگر خالی باشد فقط روی context_data لاگ می‌شود
    LMS_INTEGRATION_SECRET: str = ""  # اختیاری: هدر X-Integration-Secret

    # الوکام (کلاس آنلاین) — https://pnlapi.alocom.co/api/documentation
    ALOCOM_ENABLED: bool = False
    ALOCOM_API_BASE: str = "https://pnlapi.alocom.co"
    ALOCOM_USERNAME: str = ""
    ALOCOM_PASSWORD: str = ""
    ALOCOM_DEFAULT_AGENT_SERVICE_ID: int = 0  # 0 = باید در بدنهٔ درخواست یا متادیتا بیاید
    # مسیرهای نسبی نسبت به ALOCOM_API_BASE (در صورت تفاوت نسخه API قابل تنظیم)
    ALOCOM_PATH_LOGIN: str = "/api/v1/auth/login"
    ALOCOM_PATH_CREATE_EVENT: str = "/api/v1/agents/events"
    ALOCOM_PATH_REGISTER_IN_EVENT: str = "/api/v1/agents/events/{event_id}/enroll-user-with-token"
    ALOCOM_PATH_CREATE_USER: str = "/api/v1/agents/users"
    # اگر True و خطای شبکه/API، به رفتار قبلی (ui_hints + وب‌هوک) برمی‌گردد
    ALOCOM_FALLBACK_TO_UI_HINTS: bool = True

    # CORS — دامنه‌های مجاز با کاما (هم‌تراز scripts/deploy_internet_host.py روی هاست).
    # لوکال با پروکسی Vite معمولاً همین لیست کافی است؛ برای origin مستقیم مثلاً :5173 را اضافه کنید.
    # مقدار * فقط برای توسعهٔ موقت؛ با allow_credentials سازگار نیست و در DEBUG=false رد می‌شود.
    # در production فقط https؛ http در production_guards رد می‌شود.
    CORS_ALLOW_ORIGINS: str = (
        "https://lms.psychoanalysis.ir,https://ims.psychoanalysis.ir"
    )

    # آغاز درمان آموزشی: مبلغ جلسهٔ اول (ریال) برای درگاه SEP وقتی در context تنظیم نشده باشد
    START_THERAPY_FIRST_SESSION_FEE_RIAL: int = 10_000_000
    # جلسه اضافی درمان آموزشی (ریال) — هم‌تراز DEFAULT_EXTRA_SESSION_FEE به تومان در PaymentService
    EXTRA_SESSION_FEE_RIAL: int = 7_500_000

    # ثبت‌نام آشنایی/جامع: اگر در context مبلغ ثبت نباشد، UI و درگاه از این مقادیر استفاده می‌کنند
    REGISTRATION_INTERVIEW_FEE_RIAL: int = 5_000_000
    # شهریه نهایی در فاکتور داخلی (تومان) — payment_amount_rial = این × 10
    REGISTRATION_TUITION_INVOICE_TOMAN: float = 120_000_000.0

    # تیکتینگ: نام کاربری مسئول اولیهٔ واحد (دریافت همهٔ تیکت‌ها و ارجاع به فرد مورد نیاز). اگر خالی باشد اولین کاربر staff فعال.
    TICKET_TRIAGE_USERNAME: str = ""

    # مدیر اصلی سایت: صندوق پیگیری اپراتورها و سایر قابلیت‌های فقط مالک — هم‌نام با users.username
    PRIMARY_SITE_ADMIN_USERNAME: str = "admin"

    # دمو: اگر true و جدول students خالی باشد، همان دیتابیس API با دادهٔ دمو پر می‌شود (بدون نیاز به اسکریپت روی میزبان)
    SEED_DEMO_ON_STARTUP: bool = False
    # اگر true باشد پس از سناریوها، ماتریس کامل فرایندها هم در پس‌زمینه اجرا می‌شود (چند دقیقه)
    SEED_DEMO_FULL_MATRIX: bool = False

    # اسلات مصاحبه: پس از انتخوسط دانشجو، مهلت تکمیل پرداخت (دقیقه)؛ بعد از آن اسلات برای دیگران آزاد می‌شود.
    INTERVIEW_BOOKING_PAYMENT_DEADLINE_MINUTES: int = 10
    # نمای راهنما — حداکثر مدت«نگهداری پیش‌پرداخت»؛ منطق آزادسازی بر اساس مهلت پرداخت بالاست.
    INTERVIEW_BOOKING_SOFT_RESERVE_MINUTES: int = 60

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE_FOR_SETTINGS,
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def effective_payment_callback_url(s: Settings | None = None) -> str:
    """آدرس کال‌بک درگاه: اگر PAYMENT_CALLBACK هنوز localhost باشد اما APP_BASE_URL پروduction باشد، از APP_BASE_URL ساخته می‌شود (شایع‌ترین علت اختلال سپ پس از SSL)."""
    st = s or get_settings()
    raw = (st.PAYMENT_CALLBACK_URL or "").strip()
    base = (st.APP_BASE_URL or "").strip().rstrip("/")
    if raw and ("localhost" in raw or "127.0.0.1" in raw) and base.startswith("https://"):
        return f"{base}/api/payment/callback"
    if raw:
        return raw
    if base:
        return f"{base}/api/payment/callback"
    return "http://localhost:3000/api/payment/callback"
