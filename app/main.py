"""
Gateway — FastAPI application.
Faces the frontend. Handles auth, rate limiting, WebSocket, proxies to orchestrator.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.Config import CORS_ORIGINS, REDIS_URL
from app.Database import engine
from app.ORM_Models import Base
from app.Middleware import RequestLoggingMiddleware
from app.Routes import router
from app.WebSocket import websocket_live

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting gateway...")

    # Create database tables (users, request_logs, etc.)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("  Database tables ready")

    # Connect Redis
    redis_conn = aioredis.from_url(REDIS_URL, decode_responses=False)
    app.state.redis = redis_conn

    logger.info("Gateway ready")
    yield

    logger.info("Shutting down...")
    await redis_conn.close()
    logger.info("Gateway stopped")


app = FastAPI(title="Emotion Recognition Gateway", version="1.0.0", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging
app.add_middleware(RequestLoggingMiddleware)

# REST routes
app.include_router(router, prefix="/api")


# WebSocket endpoint
@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket):
    await websocket_live(websocket)


# Health check — root level, used by Docker health check
@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}