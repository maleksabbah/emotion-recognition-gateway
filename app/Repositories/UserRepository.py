"""
UserRepository — DB access for the users table.

Services call these methods; they never touch SQLAlchemy directly.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.Entities.User import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Reads ──────────────────────────────────────────

    async def find_by_id(self, user_id: str | uuid.UUID) -> Optional[User]:
        uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
        result = await self.db.execute(select(User).where(User.id == uid))
        return result.scalar_one_or_none()

    async def find_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def find_by_username(self, username: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        return (await self.find_by_email(email)) is not None

    async def username_exists(self, username: str) -> bool:
        return (await self.find_by_username(username)) is not None

    # ── Writes ─────────────────────────────────────────

    async def create(self, email: str, username: str, hashed_password: str) -> User:
        user = User(
            email=email,
            username=username,
            hashed_password=hashed_password,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update_last_login(self, user_id: str | uuid.UUID) -> None:
        uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
        await self.db.execute(
            update(User)
            .where(User.id == uid)
            .values(last_login=datetime.now(timezone.utc))
        )
        await self.db.commit()