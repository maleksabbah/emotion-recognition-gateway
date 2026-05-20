"""
Async SQLAlchemy engine and session factory for gateway_db.

dependencies.py builds a SessionLocal() per request and yields it.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.Config.Config import GATEWAY_DB_URL


engine = create_async_engine(
    GATEWAY_DB_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)