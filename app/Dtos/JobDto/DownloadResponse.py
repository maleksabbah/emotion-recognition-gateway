from __future__ import annotations

from pydantic import BaseModel


class DownloadResponse(BaseModel):
    download_url: str
    filename: str