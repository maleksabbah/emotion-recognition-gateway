from __future__ import annotations

from pydantic import BaseModel


class UploadResponse(BaseModel):
    session_id: str
    upload_url: str
    s3_key: str