"""
Gateway REST API routes.
All requests proxy to the orchestrator. Gateway handles auth, rate limiting, logging.
"""
from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from app.Auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    create_user,
    decode_token,
    get_current_user,
    get_user_by_id,
)
from app.Config import ACCESS_TOKEN_EXPIRE_MINUTES, ORCHESTRATOR_URL
from app.Middleware import enforce_rate_limit
from app.ORM_Models import User
from app.Schemas import (
    DownloadResponse,
    HealthResponse,
    LiveSessionResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    SessionStatusResponse,
    TokenResponse,
    UploadCompleteRequest,
    UploadRequest,
    UploadResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ══════════════════════════════════════════════
# Health
# ══════════════════════════════════════════════

@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse()


# ══════════════════════════════════════════════
# Auth
# ══════════════════════════════════════════════

@router.post("/auth/register", response_model=UserResponse)
async def register(req: RegisterRequest):
    user = await create_user(email=req.email, username=req.username, password=req.password)
    return UserResponse(
        id=str(user.id),
        email=user.email,
        username=user.username,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post("/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    user = await authenticate_user(email=req.email, password=req.password)
    access_token = create_access_token(str(user.id), user.email)
    refresh_token = create_refresh_token(str(user.id))
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest):
    payload = decode_token(req.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user = await get_user_by_id(payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid user")

    access_token = create_access_token(str(user.id), user.email)
    refresh_token = create_refresh_token(str(user.id))
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/auth/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(user.id),
        email=user.email,
        username=user.username,
        is_active=user.is_active,
        created_at=user.created_at,
    )


# ══════════════════════════════════════════════
# Upload (pre-signed URL flow)
# ══════════════════════════════════════════════

@router.post("/upload/request", response_model=UploadResponse)
async def request_upload(
    req: UploadRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    await enforce_rate_limit(request)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/api/sessions",
                json={
                    "mode": req.mode,
                    "metadata": {
                        "user_id": str(user.id),
                        "filename": req.filename,
                        "content_type": req.content_type,
                    },
                },
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail="Orchestrator error")
            session_data = resp.json()

            resp = await client.post(
                f"{ORCHESTRATOR_URL}/api/upload/presign",
                json={
                    "session_id": session_data["session_id"],
                    "filename": req.filename,
                    "content_type": req.content_type,
                },
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail="Failed to get upload URL")
            presign_data = resp.json()

    except httpx.RequestError as e:
        logger.error(f"Orchestrator request failed: {e}")
        raise HTTPException(status_code=502, detail="Orchestrator unreachable")

    return UploadResponse(
        session_id=session_data["session_id"],
        upload_url=presign_data["upload_url"],
        s3_key=presign_data["s3_key"],
    )


@router.post("/upload/complete")
async def upload_complete(
    req: UploadCompleteRequest,
    user: User = Depends(get_current_user),
):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/api/upload-job",
                json={
                    "session_id": req.session_id,
                    "mode": "video",
                    "s3_key": f"uploads/{req.session_id}/",
                },
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail="Orchestrator error")
            return resp.json()
    except httpx.RequestError as e:
        logger.error(f"Orchestrator request failed: {e}")
        raise HTTPException(status_code=502, detail="Orchestrator unreachable")


# ══════════════════════════════════════════════
# Session status + download
# ══════════════════════════════════════════════

@router.get("/sessions/{session_id}/status", response_model=SessionStatusResponse)
async def session_status(
    session_id: str,
    user: User = Depends(get_current_user),
):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{ORCHESTRATOR_URL}/api/sessions/{session_id}/status")
            if resp.status_code == 404:
                raise HTTPException(status_code=404, detail="Session not found")
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail="Orchestrator error")
            return resp.json()
    except httpx.RequestError as e:
        logger.error(f"Orchestrator request failed: {e}")
        raise HTTPException(status_code=502, detail="Orchestrator unreachable")


@router.get("/sessions/{session_id}/download", response_model=DownloadResponse)
async def session_download(
    session_id: str,
    user: User = Depends(get_current_user),
):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{ORCHESTRATOR_URL}/api/sessions/{session_id}/download")
            if resp.status_code == 404:
                raise HTTPException(status_code=404, detail="Session not found")
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail="Orchestrator error")
            return resp.json()
    except httpx.RequestError as e:
        logger.error(f"Orchestrator request failed: {e}")
        raise HTTPException(status_code=502, detail="Orchestrator unreachable")


@router.get("/sessions")
async def list_sessions(user: User = Depends(get_current_user)):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{ORCHESTRATOR_URL}/api/sessions")
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail="Orchestrator error")
            return resp.json()
    except httpx.RequestError as e:
        logger.error(f"Orchestrator request failed: {e}")
        raise HTTPException(status_code=502, detail="Orchestrator unreachable")








