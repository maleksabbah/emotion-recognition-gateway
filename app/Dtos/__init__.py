"""
Gateway DTOs — grouped by domain, one class per file.

Layout:
    app/Dtos/
      UserDto/      RegisterRequest, RegisterResponse, UserResponse
      AuthDto/      LoginRequest, RefreshRequest, LoginResponse, RefreshResponse
      UploadDto/    UploadRequest, UploadCompleteRequest, UploadResponse, UploadCompleteResponse
      JobDto/   SessionResponse, SessionStatusResponse, DownloadResponse
      HealthDto/    HealthResponse

Import any of three ways:
    from app.Dtos import RegisterRequest, LoginResponse
    from app.Dtos.UserDto import RegisterRequest
    from app.Dtos.UserDto.RegisterRequest import RegisterRequest
"""

# ── UserDto ────────────────────────────────────────────
from app.Dtos.UserDto.RegisterRequest import RegisterRequest
from app.Dtos.UserDto.RegisterResponse import RegisterResponse
from app.Dtos.UserDto.UserResponse import UserResponse

# ── AuthDto ────────────────────────────────────────────
from app.Dtos.AuthDto.LoginRequest import LoginRequest
from app.Dtos.AuthDto.RefreshRequest import RefreshRequest
from app.Dtos.AuthDto.LoginResponse import LoginResponse
from app.Dtos.AuthDto.RefreshResponse import RefreshResponse

# ── UploadDto ──────────────────────────────────────────
from app.Dtos.UploadDto.UploadRequest import UploadRequest
from app.Dtos.UploadDto.UploadCompleteRequest import UploadCompleteRequest
from app.Dtos.UploadDto.UploadResponse import UploadResponse
from app.Dtos.UploadDto.UploadCompleteResponse import UploadCompleteResponse

# ── JobDto ─────────────────────────────────────────
from app.Dtos.JobDto.JobResponse import JobResponse
from app.Dtos.JobDto.JobStatusResponse import JobStatusResponse
from app.Dtos.JobDto.DownloadResponse import DownloadResponse

# ── HealthDto ──────────────────────────────────────────


__all__ = [
    # UserDto
    "RegisterRequest",
    "RegisterResponse",
    "UserResponse",
    # AuthDto
    "LoginRequest",
    "RefreshRequest",
    "LoginResponse",
    "RefreshResponse",
    # UploadDto
    "UploadRequest",
    "UploadCompleteRequest",
    "UploadResponse",
    "UploadCompleteResponse",
    # JobDto
    "JobResponse",
    "JobStatusResponse",
    "DownloadResponse",

]