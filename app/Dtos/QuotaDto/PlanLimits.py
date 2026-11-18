from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class PlanLimits(BaseModel):
    """Every limit field of a plan. None = unlimited (admins)."""
    photos_per_month: Optional[int] = None
    videos_per_month: Optional[int] = None
    max_image_bytes: Optional[int] = None
    max_video_bytes: Optional[int] = None
    max_video_seconds: Optional[int] = None
    uploads_per_hour: Optional[int] = None
    max_concurrent_jobs: Optional[int] = None
    live_minutes_per_month: Optional[int] = None
    live_session_max_seconds: Optional[int] = None
