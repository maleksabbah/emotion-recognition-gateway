"""
Config package — env vars, DB engine, Redis factory.

Re-exports the common things so callers can write:
    from app.Config import SessionLocal, get_redis, JWT_SECRET
"""
from app.Config.Config import (
    # Auth
    JWT_SECRET,
    JWT_ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    BCRYPT_ROUNDS,
    # Postgres
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    GATEWAY_DB,
    GATEWAY_DB_URL,
    # Redis
    REDIS_HOST,
    REDIS_PORT,
    REDIS_URL,
    # Downstream
    ORCHESTRATOR_URL,
    STORAGE_SERVICE_URL,
    # CORS
    CORS_ORIGINS,
    # Rate limiting
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
    UPLOAD_RATE_LIMIT,
    UPLOAD_RATE_WINDOW_SECONDS,
)
from app.Config.Database import engine, SessionLocal
from app.Config.Redis import get_redis

__all__ = [
    # Auth
    "JWT_SECRET",
    "JWT_ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "REFRESH_TOKEN_EXPIRE_DAYS",
    "BCRYPT_ROUNDS",
    # Postgres
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "GATEWAY_DB",
    "GATEWAY_DB_URL",
    # Redis
    "REDIS_HOST",
    "REDIS_PORT",
    "REDIS_URL",
    # Downstream
    "ORCHESTRATOR_URL",
    "STORAGE_SERVICE_URL",
    # CORS
    "CORS_ORIGINS",
    # Rate limiting
    "RATE_LIMIT_REQUESTS",
    "RATE_LIMIT_WINDOW_SECONDS",
    "UPLOAD_RATE_LIMIT",
    "UPLOAD_RATE_WINDOW_SECONDS",
    # DB
    "engine",
    "SessionLocal",
    # Redis factory
    "get_redis",
]