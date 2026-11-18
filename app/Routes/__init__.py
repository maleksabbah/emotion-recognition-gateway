"""
Gateway routes — FastAPI routers grouped by domain.

main.py imports the routers and mounts them under /api.

  HealthRoutes   /health
  AuthRoutes     /auth/register, /auth/login, /auth/refresh
  UserRoutes     /auth/me
  UploadRoutes   /upload/request, /upload/complete
  JobRoutes      /sessions, /sessions/{id}/status, /sessions/{id}/download
  QuotaRoutes    /plans, /auth/quota
"""
from app.Routes.HealthRoutes import router as health_router
from app.Routes.AuthRoutes import router as auth_router
from app.Routes.UserRoutes import router as user_router
from app.Routes.UploadRoutes import router as upload_router
from app.Routes.JobRoutes import router as job_router
from app.Routes.QuotaRoutes import router as quota_router

__all__ = [
    "health_router",
    "auth_router",
    "user_router",
    "upload_router",
    "job_router",
    "quota_router",
]