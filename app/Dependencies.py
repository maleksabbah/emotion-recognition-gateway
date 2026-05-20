"""
FastAPI dependency factories.

One place where per-request services are assembled with their repos and
clients. Rate limiting + current-user resolution live here too — they're
per-request concerns, not services.
"""
from __future__ import annotations

from typing import AsyncIterator

import httpx
import redis.asyncio as redis
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.Config.Database import SessionLocal
from app.Config.Config import (
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
    UPLOAD_RATE_LIMIT,
    UPLOAD_RATE_WINDOW_SECONDS,
)
from app.Entities.User import User
from app.Exceptions import RateLimitExceeded
from app.Repositories.UserRepository import UserRepository
from app.Repositories.OrchestratorClient import OrchestratorClient
from app.Repositories.StorageClient import StorageClient
from app.Repositories.RedisRepository import RedisRepository
from app.Services.AuthService import AuthService
from app.Services.UserService import UserService
from app.Services.JobProxyService import JobProxyService
from app.Services.FileProxyService import FileProxyService


# ─── Per-request DB session ────────────────────────────────────────────

async def get_db_session() -> AsyncIterator[AsyncSession]:
    session = SessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# ─── Shared infra (built once at startup, stored on app.state) ─────────

def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


def get_redis_conn(request: Request) -> redis.Redis:
    return request.app.state.redis


# ─── Repositories ──────────────────────────────────────────────────────

def get_user_repo(
    session: AsyncSession = Depends(get_db_session),
) -> UserRepository:
    return UserRepository(session)


def get_orchestrator_client(
    http: httpx.AsyncClient = Depends(get_http_client),
) -> OrchestratorClient:
    return OrchestratorClient(http)


def get_storage_client(
    http: httpx.AsyncClient = Depends(get_http_client),
) -> StorageClient:
    return StorageClient(http)


def get_redis_repo(
    conn: redis.Redis = Depends(get_redis_conn),
) -> RedisRepository:
    return RedisRepository(conn)


# ─── Services ──────────────────────────────────────────────────────────

def get_auth_service(
    users: UserRepository = Depends(get_user_repo),
) -> AuthService:
    return AuthService(users=users)


def get_user_service(
    users: UserRepository = Depends(get_user_repo),
) -> UserService:
    return UserService(users=users)


def get_job_proxy_service(
    client: OrchestratorClient = Depends(get_orchestrator_client),
) -> JobProxyService:
    return JobProxyService(orchestrator=client)


def get_file_proxy_service(
    orchestrator: OrchestratorClient = Depends(get_orchestrator_client),
    storage: StorageClient = Depends(get_storage_client),
) -> FileProxyService:
    return FileProxyService(orchestrator=orchestrator, storage=storage)


# ─── Current user resolution ───────────────────────────────────────────

async def get_current_user(
    request: Request,
    auth: AuthService = Depends(get_auth_service),
) -> User:
    return await auth.resolve_current_user(request)


# ─── Rate limiting ─────────────────────────────────────────────────────
#
# Per-route dependency. Reads policy from path and increments a Redis
# counter scoped to (ip, path). Raises RateLimitExceeded on breach.
# Fails open on Redis errors — never blocks traffic because cache is sick.

async def enforce_rate_limit(
    request: Request,
    redis_repo: RedisRepository = Depends(get_redis_repo),
) -> None:
    ip = request.client.host if request.client else "unknown"
    path = str(request.url.path)
    max_requests, window = _rate_limit_policy(path)
    key = RedisRepository.rate_key(ip, path)

    try:
        count = await redis_repo.incr_with_expiry(key, window)
    except Exception:
        # Fail open — log + allow.
        return

    if count > max_requests:
        raise RateLimitExceeded()


def _rate_limit_policy(path: str) -> tuple[int, int]:
    if "/upload" in path:
        return UPLOAD_RATE_LIMIT, UPLOAD_RATE_WINDOW_SECONDS
    return RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW_SECONDS
