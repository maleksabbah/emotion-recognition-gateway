from __future__ import annotations

from pydantic import BaseModel


class UploadCompleteResponse(BaseModel):
    status: str
    session_id: str