from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from app.Dtos.QuotaDto.PlanLimits import PlanLimits


class QuotaUsage(BaseModel):
    """This month's usage from the orchestrator. None = couldn't be fetched."""
    photos: Optional[int] = None
    videos: Optional[int] = None
    live_seconds: Optional[int] = None
    active_jobs: Optional[int] = None


class QuotaResponse(BaseModel):
    """GET /api/auth/quota."""
    plan: str
    unlimited: bool
    limits: PlanLimits
    usage: QuotaUsage
    usage_available: bool
    period_start: str
    resets_at: str
