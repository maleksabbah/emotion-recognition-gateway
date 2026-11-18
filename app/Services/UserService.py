"""
UserService — owns the user record.

Currently a single use case: load the user behind a JWT for /me. As the
product grows (profile updates, quota, preferences) the methods land here.

Pure DI: takes a UserRepository.
"""
from __future__ import annotations

from app.Dtos.UserDto.UserResponse import UserResponse
from app.Entities.User import User
from app.Exceptions import AccountDisabled, UserNotFound
from app.Repositories.UserRepository import UserRepository


class UserService:
    def __init__(self, users: UserRepository):
        self.users = users

    async def get_me(self, user_id: str) -> UserResponse:
        """
        Load an active user by id. Raises UserNotFound / AccountDisabled.
        Callers (e.g. /me controller, WS auth) decode the JWT first, then
        pass the sub here.
        """
        user = await self.users.find_by_id(user_id)
        if not user:
            raise UserNotFound()
        if not user.is_active:
            raise AccountDisabled()
        return UserResponse.model_validate({
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "is_active": user.is_active,
            "created_at": user.created_at,
        })

    async def load_active_user(self, user_id: str) -> User:
        """
        Same lookup but returns the raw User entity. Used wherever the
        caller needs the entity itself (WS auth, rate limit by user, etc.)
        rather than a DTO.
        """
        user = await self.users.find_by_id(user_id)
        if not user:
            raise UserNotFound()
        if not user.is_active:
            raise AccountDisabled()
        return user