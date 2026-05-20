from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RegisterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    username: str
    is_active: bool
    created_at: datetime