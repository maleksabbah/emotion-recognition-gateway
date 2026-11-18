from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class UploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=128)
    mode: Literal["video", "photo"] = "video"
    # Declared size in bytes. Checked against the plan, then signed into the
    # presigned PUT (Content-Length) so storage rejects a different-size body.
    size: int = Field(gt=0)