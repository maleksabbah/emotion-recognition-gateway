from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class JobStatusResponse(BaseModel):
    session_id: str
    status: str
    progress: float = 0.0
    current_frame: int = 0
    total_frames: int = 0
    eta_seconds: Optional[float] = None