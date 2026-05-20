"""
AuthService — proves who you are.

Owns: password hashing, JWT create+decode, register flow, login flow,
refresh flow. Loading a user by id for /me lives in UserService.

Pure DI: takes a UserRepository. Raises DomainException subclasses;
the central handler maps to HTTP.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.Config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    BCRYPT_ROUNDS,
    JWT_ALGORITHM,
    JWT_SECRET,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from app.Dtos.AuthDto.LoginRequest import LoginRequest
from app.Dtos.AuthDto.LoginResponse import LoginResponse
from app.Dtos.AuthDto.RefreshRequest import RefreshRequest
from app.Dtos.AuthDto.RefreshResponse import RefreshResponse
from app.Dtos.UserDto.RegisterRequest import RegisterRequest
from app.Dtos.UserDto.RegisterResponse import RegisterResponse
from app.Entities.User import User
from app.Exceptions import (
    AccountDisabled,
    EmailAlreadyRegistered,
    InvalidCredentials,
    InvalidToken,
    InvalidTokenType,
    MissingAuth,
    TokenExpired,
    UserNotFound,
    UsernameAlreadyTaken,
)
from app.Repositories.UserRepository import UserRepository


class AuthService:
    def __init__(self, users: UserRepository):
        self.users = users

    # ══════════════════════════════════════════
    # Use cases
    # ══════════════════════════════════════════

    async def register(self, req: RegisterRequest) -> RegisterResponse:
        if await self.users.email_exists(req.email):
            raise EmailAlreadyRegistered()
        if await self.users.username_exists(req.username):
            raise UsernameAlreadyTaken()

        user = await self.users.create(
            email=req.email,
            username=req.username,
            hashed_password=self._hash_password(req.password),
        )
        return RegisterResponse.model_validate(_to_dict(user))

    async def login(self, req: LoginRequest) -> LoginResponse:
        user = await self.users.find_by_email(req.email)
        if not user or not self._verify_password(req.password, user.hashed_password):
            raise InvalidCredentials()
        if not user.is_active:
            raise AccountDisabled()

        await self.users.update_last_login(user.id)
        return self._issue_tokens(LoginResponse, user)

    async def refresh(self, req: RefreshRequest) -> RefreshResponse:
        payload = self._decode_token(req.refresh_token)
        if payload.get("type") != "refresh":
            raise InvalidTokenType()

        user = await self.users.find_by_id(payload["sub"])
        if not user:
            raise UserNotFound()
        if not user.is_active:
            raise AccountDisabled()

        return self._issue_tokens(RefreshResponse, user)

    def decode_access_token(self, token: str) -> dict[str, Any]:
        """
        Decode an access token and validate its type. Returns the payload.
        UserService.load_active_user uses this to look up /me.
        """
        payload = self._decode_token(token)
        if payload.get("type") != "access":
            raise InvalidTokenType()
        return payload

    async def resolve_current_user(self, request) -> User:
        """
        Extract the bearer token from the Authorization header, decode it,
        load and return the User entity. Used by the get_current_user
        dependency from HTTP routes.
        """
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise MissingAuth()

        token = auth_header.split(" ", 1)[1]
        payload = self.decode_access_token(token)

        user = await self.users.find_by_id(payload["sub"])
        if not user:
            raise UserNotFound()
        if not user.is_active:
            raise AccountDisabled()
        return user

    async def resolve_user_from_token(self, token: str) -> User:
        """
        Same as resolve_current_user, but pulls the token straight (used
        by WebSocket handlers where the token arrives as ?token=...).
        """
        if not token:
            raise MissingAuth()
        payload = self.decode_access_token(token)
        user = await self.users.find_by_id(payload["sub"])
        if not user:
            raise UserNotFound()
        if not user.is_active:
            raise AccountDisabled()
        return user

    # ══════════════════════════════════════════
    # Internal — passwords
    # ══════════════════════════════════════════

    @staticmethod
    def _hash_password(password: str) -> str:
        return bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(rounds=BCRYPT_ROUNDS),
        ).decode("utf-8")

    @staticmethod
    def _verify_password(password: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
        except ValueError:
            return False

    # ══════════════════════════════════════════
    # Internal — JWT
    # ══════════════════════════════════════════

    def _issue_tokens(self, response_cls, user: User):
        access = self._create_access_token(str(user.id), user.email)
        refresh = self._create_refresh_token(str(user.id))
        return response_cls(
            access_token=access,
            refresh_token=refresh,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    @staticmethod
    def _create_access_token(user_id: str, email: str) -> str:
        payload = {
            "sub": user_id,
            "email": email,
            "type": "access",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    @staticmethod
    def _create_refresh_token(user_id: str) -> str:
        payload = {
            "sub": user_id,
            "type": "refresh",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    @staticmethod
    def _decode_token(token: str) -> dict[str, Any]:
        try:
            return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise TokenExpired()
        except jwt.InvalidTokenError:
            raise InvalidToken()


# ── helpers ────────────────────────────────────────────

def _to_dict(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "is_active": user.is_active,
        "created_at": user.created_at,
    }