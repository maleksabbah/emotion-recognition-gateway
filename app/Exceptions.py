"""
Domain exceptions + central FastAPI handler.

Services raise these. They never raise HTTPException directly. The handler
registered in main.py converts subclasses to JSON responses.

Adding a new failure case:
  1. Subclass DomainException (or one of the category bases below).
  2. Set status_code and default_detail on the subclass.
  3. The handler picks it up automatically — no extra wiring.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger("gateway.exceptions")


# ══════════════════════════════════════════════
# Base
# ══════════════════════════════════════════════

class DomainException(Exception):
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail: str = "Internal server error"

    def __init__(self, detail: Optional[str] = None):
        self.detail = detail or self.default_detail
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
    default_detail = "User not found"


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
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Wire the handler into a FastAPI app. Call from main.py."""
    app.add_exception_handler(DomainException, domain_exception_handler)