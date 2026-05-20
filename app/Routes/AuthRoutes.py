"""
Auth routes — identity verification flows.

  POST /auth/register   create an account
  POST /auth/login      exchange credentials for tokens
  POST /auth/refresh    exchange refresh token for new tokens
"""
from fastapi import APIRouter, Depends

from app.Dtos.UserDto.RegisterRequest import RegisterRequest
from app.Dtos.UserDto.RegisterResponse import RegisterResponse
from app.Dtos.AuthDto.LoginRequest import LoginRequest
from app.Dtos.AuthDto.LoginResponse import LoginResponse
from app.Dtos.AuthDto.RefreshRequest import RefreshRequest
from app.Dtos.AuthDto.RefreshResponse import RefreshResponse
from app.Services.AuthService import AuthService
from app.Dependencies import get_auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse)
async def register(
    req: RegisterRequest,
    auth: AuthService = Depends(get_auth_service),
) -> RegisterResponse:
    return await auth.register(req)


@router.post("/login", response_model=LoginResponse)
async def login(
    req: LoginRequest,
    auth: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    return await auth.login(req)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    req: RefreshRequest,
    auth: AuthService = Depends(get_auth_service),
) -> RefreshResponse:
    return await auth.refresh(req)