"""
Pydantic models for gateway API requests and responses.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ──────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    is_active: bool
    created_at: datetime


# ──────────────────────────────────────────────
# Upload
# ──────────────────────────────────────────────
class UploadRequest(BaseModel):
    filename: str
    content_type: str
    mode: str = "video"  # "video" or "photo"


class UploadResponse(BaseModel):
    session_id: str
    upload_url: str
    s3_key: str


class UploadCompleteRequest(BaseModel):
    session_id: str


# ──────────────────────────────────────────────
# Session
# ──────────────────────────────────────────────
class SessionStatusResponse(BaseModel):
    session_id: str
    status: str
    progress: float = 0.0
    total_frames: int = 0
    current_frame: int = 0
    eta_seconds: Optional[float] = None


class DownloadResponse(BaseModel):
    download_url: str
    filename: str


# ──────────────────────────────────────────────
# Live
# ──────────────────────────────────────────────
class LiveSessionResponse(BaseModel):
    session_id: str
    status: str = "active"


# ──────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────
class HealthResponse(BaseModel):
    service: str = "gateway"
    status: str = "ok"
    version: str = "1.0.0"