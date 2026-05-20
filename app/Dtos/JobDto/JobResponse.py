from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    mode: str
    status: str
    created_at: datetime
    total_frames: int = 0
    total_faces: int = 0
    burned_s3_key: Optional[str] = None