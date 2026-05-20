from __future__ import annotations

from pydantic import BaseModel


class UploadCompleteRequest(BaseModel):
    session_id: str