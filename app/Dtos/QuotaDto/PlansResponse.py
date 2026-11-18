from __future__ import annotations

from pydantic import BaseModel


class PlanInfo(BaseModel):
    """One plan in GET /api/plans — name, availability, then every limit field."""
    name: str
    available: bool
    photos_per_month: int
    videos_per_month: int
    max_image_bytes: int
    max_video_bytes: int
    max_video_seconds: int
    uploads_per_hour: int
    max_concurrent_jobs: int
    live_minutes_per_month: int
    live_session_max_seconds: int


class PlansResponse(BaseModel):
    plans: list[PlanInfo]
