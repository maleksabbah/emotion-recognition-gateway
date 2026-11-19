"""
Gateway configuration — environment variables loaded once.

Anything tunable via env goes here. Subsystems (Database, Redis) read
from this module, not from os.getenv directly.
"""
from __future__ import annotations

import os
import re


# ─── JWT / Auth ────────────────────────────────────────────────────────

JWT_SECRET = os.environ["JWT_SECRET_KEY"]
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "12"))


# ─── PostgreSQL (gateway_db) ───────────────────────────────────────────

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "emotion")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
GATEWAY_DB = os.getenv("GATEWAY_DB", "gateway_db")
# Honor DATABASE_URL if set (e.g. RDS); otherwise compose from the parts.
def _asyncpg_url(url: str) -> str:
    """
    Normalise a provider URL for SQLAlchemy + asyncpg. Railway/Supabase hand
    out postgres:// or postgresql://; asyncpg also rejects libpq's sslmode=,
    so map it to its own ssl= parameter.
    """
    url = re.sub(r"^postgres(ql)?://", "postgresql+asyncpg://", url)
    return re.sub(r"([?&])sslmode=", r"\1ssl=", url)


_DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not _DATABASE_URL and not POSTGRES_PASSWORD:
    raise RuntimeError("Set DATABASE_URL, or POSTGRES_PASSWORD with the POSTGRES_* parts")

GATEWAY_DB_URL = _asyncpg_url(_DATABASE_URL) if _DATABASE_URL else (
    f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{GATEWAY_DB}"
)


# ─── Redis ─────────────────────────────────────────────────────────────

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_URL = os.getenv("REDIS_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}")


# ─── Downstream services ──────────────────────────────────────────────

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8001")
STORAGE_SERVICE_URL = os.getenv("STORAGE_SERVICE_URL", "http://storage:8002")


# ─── CORS ─────────────────────────────────────────────────────────────

CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
).split(",")


# ─── Rate limiting ────────────────────────────────────────────────────



# ─── Kafka (SASL) ────────────────────────────────────────────────────
KAFKA_SASL_USERNAME = os.getenv("KAFKA_SASL_USERNAME", "")
KAFKA_SASL_PASSWORD = os.getenv("KAFKA_SASL_PASSWORD", "")


# ─── Rate limiting ────────────────────────────────────────────────────

RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "500"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
UPLOAD_RATE_LIMIT = int(os.getenv("UPLOAD_RATE_LIMIT", "60"))
UPLOAD_RATE_WINDOW_SECONDS = int(os.getenv("UPLOAD_RATE_WINDOW_SECONDS", "60"))


# ─── Plans ────────────────────────────────────────────────────────────
#
# The plans table (gateway_db.plans) is the source of truth. These are only
# the DEFAULTS: on boot, any plan below without a row is inserted with these
# numbers; an existing row is never overwritten, so edit the row (not this
# file) to change a live plan. They're also the fallback if a row is missing.
# Each numeric default can be overridden via env before first seeding:
# PLAN_<NAME>_<FIELD>, e.g. PLAN_FREE_PHOTOS_PER_MONTH=100.
# Admins (users.is_admin) bypass every limit. Monthly period = UTC calendar
# month. The live_* numbers reach the orchestrator inside each access token.

DEFAULT_PLAN = "free"

_MB = 1024 * 1024

PLAN_LIMIT_FIELDS = (
    "photos_per_month",
    "videos_per_month",
    "max_image_bytes",
    "max_video_bytes",
    "max_video_seconds",
    "uploads_per_hour",
    "max_concurrent_jobs",
    "live_minutes_per_month",
    "live_session_max_seconds",
)


def _plan(name: str, available: bool, price_cents_monthly: int, **limits: int) -> dict:
    # price_cents_monthly is display-only for now (no billing yet): 0 = free.
    out: dict = {
        "name": name,
        "available": available,
        "price_cents_monthly": int(os.getenv(f"PLAN_{name.upper()}_PRICE_CENTS_MONTHLY", str(price_cents_monthly))),
        "currency": "usd",
    }
    for field in PLAN_LIMIT_FIELDS:
        env_key = f"PLAN_{name.upper()}_{field.upper()}"
        out[field] = int(os.getenv(env_key, str(limits[field])))
    return out


PLANS: dict[str, dict] = {
    "free": _plan(
        "free",
        available=True,
        price_cents_monthly=0,
        photos_per_month=50,
        videos_per_month=5,
        max_image_bytes=10 * _MB,
        max_video_bytes=50 * _MB,
        max_video_seconds=30,
        uploads_per_hour=20,
        max_concurrent_jobs=1,
        live_minutes_per_month=15,
        live_session_max_seconds=120,
    ),
    "pro": _plan(
        "pro",
        available=False,  # coming soon — not purchasable yet
        price_cents_monthly=1000,  # $10 / month
        photos_per_month=1000,
        videos_per_month=100,
        max_image_bytes=25 * _MB,
        max_video_bytes=500 * _MB,
        max_video_seconds=300,
        uploads_per_hour=200,
        max_concurrent_jobs=3,
        live_minutes_per_month=300,
        live_session_max_seconds=1800,
    ),
}