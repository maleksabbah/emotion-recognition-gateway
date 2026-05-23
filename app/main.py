"""
Gateway entry point.

Wires the FastAPI app:
  - Lifespan: build the shared httpx client and Redis connection, plus
              ensure the gateway_db schema exists (create_all for now;
              alembic later when migrations are added).
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
from sqlalchemy.ext.asyncio import create_async_engine

from app.Config import CORS_ORIGINS, GATEWAY_DB_URL, get_redis
from app.Entities import Base
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

    Schema is created via Base.metadata.create_all so a fresh deploy
    works without manual psql. Once migrations exist this can be
    swapped for alembic upgrade.
    """
    logger.info("Starting gateway...")

    # Ensure schema before serving requests.
    schema_engine = create_async_engine(GATEWAY_DB_URL)
    try:
        async with schema_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Schema ensured")
    finally:
        await schema_engine.dispose()

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