"""
Health routes — liveness check for Docker / load balancer.

No auth, no rate limit, no dependencies. Returns 200 if the process is up.
"""
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "gateway"}