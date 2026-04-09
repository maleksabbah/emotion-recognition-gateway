"""
Middleware — request logging to gateway_db, Redis-based rate limiting.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

import redis.asyncio as redis
from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.Config import (
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
    UPLOAD_RATE_LIMIT,
    UPLOAD_RATE_WINDOW_SECONDS,
)
from app.Database import async_session
from app.ORM_Models import RequestLog

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every request to gateway_db."""
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Extract user_id from request state if auth middleware set it
        user_id = getattr(request.state, "user_id", None) if hasattr(request, "state") else None

        try:
            async with async_session() as db:
                log_entry = RequestLog(
                    id = uuid.uuid4(),
                    user_id = user_id,
                    method = request.method,
                    path = str(request.url.path),
                    status_code = response.status_code,
                    response_time_ms = elapsed_ms,
                    ip_address = request.client.host if request.client else "unknown",
                    user_agent = request.headers.get("user-agent",""),


                )
                db.add(log_entry)
                await db.commit()

        except Exception as e:
            logger.error(f"Failed to log request: {e}")
        return response

# ──────────────────────────────────────────────
# Rate limiting (Redis-based)
# ──────────────────────────────────────────────

async def check_rate_limit(
        redis_conn: redis.Redis,
        key: str,
        max_requests: int,
        window_seconds: int,


) -> bool:
    """Returns True if request is allowed, False if rate limited."""
    pipe = redis_conn.pipeline()
    pipe.incr(key)
    pipe.expire(key,window_seconds)
    results = await pipe.execute()
    count = results[0]
    return count <= max_requests

async def enforce_rate_limit(request: Request) -> None:
    """Call from routes to enforce rate limiting."""
    redis_conn = request.app.state.redis
    if not redis_conn:
        return

    ip = request.client.host if request.client else "unknown"
    key = f"rate:{ip}:{request.url.path}"

    # Use upload-specific limits for upload endpoints
    if "/upload" in request.url.path:
        allowed = await check_rate_limit(redis_conn, key, UPLOAD_RATE_LIMIT,UPLOAD_RATE_WINDOW_SECONDS)
    else:
        allowed = await check_rate_limit(redis_conn,key,RATE_LIMIT_REQUESTS,RATE_LIMIT_WINDOW_SECONDS)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded, please try again later",
        )










