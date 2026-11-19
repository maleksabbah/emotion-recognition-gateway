"""
Domain exceptions + central FastAPI handler.

Services raise these. They never raise HTTPException directly. The handler
registered in main.py converts subclasses to JSON responses.

Adding a new failure case:
  1. Subclass DomainException (or one of the category bases below).
  2. Set status_code and default_detail on the subclass.
  3. The handler picks it up automatically — no extra wiring.

Limit errors (plans/quotas) also set `code`; the handler then adds it to the
body, plus any `extra` fields and `headers` the exception carries. Errors
without a code keep the plain {"detail": ...} body.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger("gateway.exceptions")


# ══════════════════════════════════════════════
# Base
# ══════════════════════════════════════════════

class DomainException(Exception):
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail: str = "Internal server error"
    code: Optional[str] = None  # machine-readable; only emitted when set

    def __init__(
        self,
        detail: Optional[str] = None,
        extra: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ):
        self.detail = detail or self.default_detail
        self.extra = extra or {}
        self.headers = headers or {}
        super().__init__(self.detail)


# ══════════════════════════════════════════════
# 4xx
# ══════════════════════════════════════════════

# --- 401 Unauthorized ---------------------------

class Unauthorized(DomainException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Unauthorized"


class MissingAuth(Unauthorized):
    default_detail = "Authentication required"


class InvalidCredentials(Unauthorized):
    default_detail = "Invalid email or password"


class TokenExpired(Unauthorized):
    default_detail = "Token expired"


class InvalidToken(Unauthorized):
    default_detail = "Invalid token"


class InvalidTokenType(Unauthorized):
    default_detail = "Invalid token type"


class UserNotFound(Unauthorized):
    # 401, not 404 — don't reveal whether a user exists
    default_detail = "Unauthorized"


# --- 403 Forbidden ------------------------------

class Forbidden(DomainException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Forbidden"


class AccountDisabled(Forbidden):
    default_detail = "Account disabled"


# --- 404 Not Found ------------------------------

class NotFound(DomainException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Not found"


# --- 409 Conflict -------------------------------

class Conflict(DomainException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict"


class EmailAlreadyRegistered(Conflict):
    default_detail = "Email already registered"


class UsernameAlreadyTaken(Conflict):
    default_detail = "Username already taken"


# --- 429 Too Many Requests ----------------------

class RateLimitExceeded(DomainException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Rate limit exceeded, please try again later"


# ══════════════════════════════════════════════
# Plan / quota limits — all carry a `code`
# ══════════════════════════════════════════════

class UploadExpired(DomainException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Upload expired, please upload again"
    code = "upload_expired"


class FileTooLarge(DomainException):
    status_code = 413  # Payload Too Large (constant name differs across starlette versions)
    default_detail = "File is too large for your plan"
    code = "file_too_large"

    def __init__(self, detail: Optional[str] = None, max_bytes: Optional[int] = None):
        extra = {"max_bytes": max_bytes} if max_bytes is not None else None
        super().__init__(detail, extra=extra)


class UploadRateLimited(DomainException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Too many uploads, please try again later"
    code = "rate_limited"

    def __init__(self, detail: Optional[str] = None, retry_after: int = 60):
        retry_after = max(1, int(retry_after))
        super().__init__(
            detail,
            extra={"retry_after": retry_after},
            headers={"Retry-After": str(retry_after)},
        )


class QuotaExceeded(DomainException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Monthly limit reached for your plan"
    code = "quota_exceeded"

    def __init__(self, detail: Optional[str] = None, resets_at: Optional[str] = None):
        super().__init__(detail, extra={"resets_at": resets_at})


class ConcurrentLimit(DomainException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Too many analyses running, wait for one to finish"
    code = "concurrent_limit"

    def __init__(self, detail: Optional[str] = None, retry_after: Optional[int] = None):
        headers = {"Retry-After": str(retry_after)} if retry_after else None
        super().__init__(detail, headers=headers)


class UsageUnavailable(DomainException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = (
        "We couldn't check your usage right now, so the upload wasn't started. "
        "Please try again in a minute."
    )
    code = "usage_unavailable"


# ══════════════════════════════════════════════
# 5xx — upstream
# ══════════════════════════════════════════════

class BadGateway(DomainException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "Bad gateway"


class OrchestratorUnreachable(BadGateway):
    default_detail = "Orchestrator unreachable"


class OrchestratorError(BadGateway):
    default_detail = "Orchestrator error"


class StorageUnreachable(BadGateway):
    default_detail = "Storage unreachable"


class StorageError(BadGateway):
    default_detail = "Storage error"


# ══════════════════════════════════════════════
# FastAPI handler
# ══════════════════════════════════════════════

async def domain_exception_handler(
    request: Request, exc: DomainException
) -> JSONResponse:
    """Map a DomainException subclass to a JSON response."""
    if exc.status_code >= 500:
        logger.error(
            "Domain 5xx on %s %s: %s",
            request.method, request.url.path, exc.detail,
        )
    else:
        logger.info(
            "Domain %s on %s %s: %s",
            exc.status_code, request.method, request.url.path, exc.detail,
        )
    content: dict[str, Any] = {"detail": exc.detail}
    if exc.code:
        content["code"] = exc.code
        content.update(exc.extra)
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=exc.headers or None,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions — log the traceback, return 500."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Wire the handler into a FastAPI app. Call from main.py."""
    app.add_exception_handler(DomainException, domain_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)