"""
Gateway repositories — boundary layer.

DB-backed:          UserRepository, RefreshTokenRepository, PlanRepository
One Redis-backed:   RedisRepository    (rate-limit only)
Two HTTP-backed:    OrchestratorClient, StorageClient

Services depend on these. Infrastructure (SQLAlchemy, redis-py, httpx)
lives only inside them.
"""
from app.Repositories.UserRepository import UserRepository
from app.Repositories.RedisRepository import RedisRepository
from app.Repositories.OrchestratorClient import OrchestratorClient
from app.Repositories.StorageClient import StorageClient
from app.Repositories.RefreshTokenRepository import RefreshTokenRepository
from app.Repositories.PlanRepository import PlanRepository

__all__ = [
    "UserRepository",
    "RedisRepository",
    "OrchestratorClient",
    "StorageClient",
    "RefreshTokenRepository",
    "PlanRepository",
]