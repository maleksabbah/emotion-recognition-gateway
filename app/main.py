"""
Gateway entry point.

Wires the FastAPI app:
  - Lifespan: build the shared httpx client and Redis connection.
  - CORS middleware.
  - Domain exception handler.
  - All routers mounted under /api (except /health at the root).
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.Config import CORS_ORIGINS, get_redis
from app.Exceptions import register_exception_handlers
from app.Routes import (
    auth_router,
    health_router,
    job_router,
    upload_router,
    user_router,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("gateway")


# ─── Lifespan ──────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Build and tear down shared resources used by dependencies.

    The httpx client is reused for every outbound call (orchestrator,
    storage). The Redis connection is used by the rate-limit dependency.
    Both are read off `app.state` in app/dependencies.py.
    """
    logger.info("Starting gateway...")

    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=5.0),
    )
    app.state.redis = get_redis()
    logger.info("Gateway ready")

    yield

    logger.info("Shutting down...")
    await app.state.http_client.aclose()
    await app.state.redis.close()
    logger.info("Gateway stopped")


# ─── App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Emotion Recognition Gateway",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

# Health stays at the root path so Docker / nginx can hit /health directly.
app.include_router(health_router)

# Everything else mounts under /api.
app.include_router(auth_router, prefix="/api")
app.include_router(user_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.include_router(job_router, prefix="/api")