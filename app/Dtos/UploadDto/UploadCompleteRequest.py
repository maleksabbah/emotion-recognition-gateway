from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class UploadCompleteRequest(BaseModel):
    """
    POST /api/upload/complete — frontend signals upload finished.
    Includes s3_key (returned by /upload/request) so the gateway can
    pass the real S3 location to the orchestrator (don't reconstruct it).
    """
    session_id: str
    s3_key: str
    mode: Optional[Literal["video", "photo"]] = "video"