"""
Async SQLAlchemy engine and session factory for gateway_db.
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.Config import GATEWAY_DB_URL

engine = create_async_engine(GATEWAY_DB_URL, echo=False, pool_size=10, max_overflow=20)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)