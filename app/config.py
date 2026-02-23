"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Tehran Institute of Psychoanalysis - انیستیتو روانکاوری تهران"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    APP_BASE_URL: str = "https://lms.psychoanalysis.ir/anistito"  # for payment callback, SMS links, etc.

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./anistito.db"
    DATABASE_URL_SYNC: str = "sqlite:///./anistito.db"
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
    SMS_API_URL: str = ""

    # Email
    EMAIL_SMTP_HOST: str = ""
    EMAIL_SMTP_PORT: int = 587
    EMAIL_FROM: str = "noreply@anistito.ir"

    # Payment
    PAYMENT_PROVIDER: str = "mock"  # "mock" | "saman" | "zibal"
    PAYMENT_CALLBACK_URL: str = "http://localhost:8000/api/payment/callback"

    # Saman (SEP) Payment Gateway
    SEP_TERMINAL_ID: str = ""
    SEP_PASSWORD: str = ""

    # Zibal Payment Gateway
    ZIBAL_MERCHANT: str = ""
    ZIBAL_SANDBOX: bool = True  # use sandbox.zibal.ir for testing

    # SLA Monitoring
    SLA_CHECK_INTERVAL_SECONDS: int = 300

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
