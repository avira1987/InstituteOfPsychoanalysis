"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Tehran Institute of Psychoanalysis - انستیتو روانکاوری تهران"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    APP_BASE_URL: str = "https://lms.psychoanalysis.ir/anistito"  # for payment callback, SMS links, etc.

    # Database (PostgreSQL only — همان مقدار در Docker: سرویس db)
    DATABASE_URL: str = "postgresql+asyncpg://anistito:anistito@localhost:5432/anistito"
    DATABASE_URL_SYNC: str = "postgresql://anistito:anistito@localhost:5432/anistito"
    DATABASE_ECHO: bool = False

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth / JWT
    SECRET_KEY: str = "change-me-in-production-use-a-real-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # SMS
    SMS_PROVIDER: str = "log"  # "log" | "mellipayamak" | "kavenegar"
    SMS_API_KEY: str = ""
    # Melipayamak OTP (rest.payamak-panel.com SendOtp) — username/password از پنل وب‌سرویس؛ نه توکن Bearer کنسول
    SMS_USERNAME: str = ""
    SMS_PASSWORD: str = ""  # اگر خالی باشد برای SendOtp از SMS_API_KEY به‌عنوان رمز وب‌سرویس استفاده می‌شود
    SMS_LINE_NUMBER: str = ""  # شماره خط برای mellipayamak (مثال: 3000xxxx)

    # ورود با پیامک (دانشجو) — کد OTP فقط برای مسیر /api/auth/otp/*
    # اگر true باشد فقط شماره‌هایی که در DB به‌عنوان کاربر فعال با نقش student ثبت شده‌اند کد می‌گیرند (ثبت‌نام اولیه باید از قبل انجام شده باشد).
    OTP_RESTRICT_TO_STUDENT_PHONES: bool = False
    # اگر true باشد، پاسخ request OTP فیلد dev_code می‌گیرد تا روی UI تست شود — در production حتماً false بگذارید.
    OTP_SHOW_CODE_IN_UI: bool = True

    # Email
    EMAIL_SMTP_HOST: str = ""
    EMAIL_SMTP_PORT: int = 587
    EMAIL_FROM: str = "noreply@anistito.ir"

    # Payment
    PAYMENT_PROVIDER: str = "mock"  # "mock" | "saman" | "zibal"
    PAYMENT_CALLBACK_URL: str = "http://localhost:3000/api/payment/callback"

    # Saman (SEP) Payment Gateway
    SEP_TERMINAL_ID: str = ""
    SEP_PASSWORD: str = ""

    # Zibal Payment Gateway
    ZIBAL_MERCHANT: str = ""
    ZIBAL_SANDBOX: bool = True  # use sandbox.zibal.ir for testing

    # SLA Monitoring
    SLA_CHECK_INTERVAL_SECONDS: int = 300

    # Calendar / time-based triggers (payment_timeout, leave reminders, session_time_reached, …)
    CALENDAR_TRIGGERS_ENABLED: bool = True
    CALENDAR_TRIGGER_INTERVAL_SECONDS: int = 300

    # Uploads (avatars, etc.)
    UPLOAD_DIR: str = "uploads"  # مسیر نسبی از روت پروژه

    # Optional outbound integration (LMS / سامانه بیرونی) — اکشن‌های «ثبت در LMS»
    LMS_INTEGRATION_WEBHOOK_URL: str = ""  # اگر خالی باشد فقط روی context_data لاگ می‌شود
    LMS_INTEGRATION_SECRET: str = ""  # اختیاری: هدر X-Integration-Secret

    # CORS — در production لیست دامنه‌ها را با کاما بگذارید (مثلاً https://lms...،https://ims...).
    # مقدار * فقط برای توسعه؛ با allow_credentials سازگار نیست.
    CORS_ALLOW_ORIGINS: str = "*"

    # تیکتینگ: نام کاربری مسئول اولیهٔ واحد (دریافت همهٔ تیکت‌ها و ارجاع به فرد مورد نیاز). اگر خالی باشد اولین کاربر staff فعال.
    TICKET_TRIAGE_USERNAME: str = ""

    # دمو: اگر true و جدول students خالی باشد، همان دیتابیس API با دادهٔ دمو پر می‌شود (بدون نیاز به اسکریپت روی میزبان)
    SEED_DEMO_ON_STARTUP: bool = False
    # اگر true باشد پس از سناریوها، ماتریس کامل فرایندها هم در پس‌زمینه اجرا می‌شود (چند دقیقه)
    SEED_DEMO_FULL_MATRIX: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
