"""
StorageClient — gateway → storage HTTP boundary.

Owns the shared httpx.AsyncClient. Services depend on this class, not on
httpx. URL paths live only here.

Methods are limited to what the gateway actually calls:
  - presign_upload    (FileProxyService.presign_upload)
  - presign_download  (FileProxyService.get_download)
  - list_files        (FileProxyService.get_download)
  - head_source       (JobProxyService.complete_upload — real uploaded size)
  - delete_source     (JobProxyService.complete_upload — drop oversize upload)
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.Config import STORAGE_SERVICE_URL
from app.Exceptions import NotFound, StorageError, StorageUnreachable
from app.Security.ServiceAuth import sign_request

logger = logging.getLogger("gateway.storage-client")


class StorageClient:
    def __init__(self, http: httpx.AsyncClient, base_url: str = STORAGE_SERVICE_URL):
        self.http = http
        self.base_url = base_url

    # ══════════════════════════════════════════
    # Presign
    # ══════════════════════════════════════════

    async def presign_upload(
        self,
        session_id: str,
        file_type: str,
        mime_type: str,
        original_filename: Optional[str] = None,
        user_id: Optional[str] = None,
        size_bytes: Optional[int] = None,
    ) -> dict:
        """
        POST /internal/presign/upload → {file_id, upload_url, s3_key}.
        size_bytes, when given, is signed into the PUT as Content-Length.
        """
        body: dict[str, Any] = {
            "session_id": session_id,
            "file_type": file_type,
            "mime_type": mime_type,
        }
        if original_filename is not None:
            body["original_filename"] = original_filename
        if user_id is not None:
            body["user_id"] = user_id
        if size_bytes is not None:
            body["size_bytes"] = size_bytes
        return await self._post("/internal/presign/upload", json=body)

    async def presign_download(self, file_id: str) -> dict:
        """POST /internal/presign/download → {download_url, file_id, file_type}."""
        return await self._post(
            "/internal/presign/download",
            json={"file_id": file_id},
        )

    # ══════════════════════════════════════════
    # File queries
    # ══════════════════════════════════════════

    async def list_files(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        category: Optional[str] = None,
        file_type: Optional[str] = None,
    ) -> list[dict]:
        params: dict[str, str] = {}
        if session_id is not None:
            params["session_id"] = session_id
        if user_id is not None:
            params["user_id"] = user_id
        if category is not None:
            params["category"] = category
        if file_type is not None:
            params["file_type"] = file_type
        data = await self._get("/internal/files", params=params)
        return data if isinstance(data, list) else []

    # ══════════════════════════════════════════
    # Session source file (uploaded by the browser)
    # ══════════════════════════════════════════

    async def head_source(self, session_id: str) -> dict:
        """
        GET /internal/sessions/{id}/source → {file_id, s3_key, size_bytes, mime_type}.
        Raises NotFound if there's no source record or the object isn't in S3.
        """
        return await self._get(f"/internal/sessions/{session_id}/source")

    async def delete_source(self, session_id: str) -> None:
        """DELETE /internal/sessions/{id}/source — removes object(s) + rows."""
        try:
            resp = await self.http.delete(
                f"{self.base_url}/internal/sessions/{session_id}/source",
                headers=sign_request({}),
            )
        except httpx.RequestError as e:
            logger.error("DELETE source for %s unreachable: %s", session_id, e)
            raise StorageUnreachable()
        if resp.status_code not in (200, 404):
            logger.error(
                "DELETE source for %s -> %s: %s", session_id, resp.status_code, resp.text
            )
            raise StorageError()

    # ══════════════════════════════════════════
    # Internal HTTP helpers
    # ══════════════════════════════════════════

    async def _get(self, path: str, params: Optional[dict] = None) -> Any:
        try:
            resp = await self.http.get(f"{self.base_url}{path}", params=params, headers=sign_request({}))
        except httpx.RequestError as e:
            logger.error("GET %s unreachable: %s", path, e)
            raise StorageUnreachable()

        if resp.status_code == 404:
            raise NotFound()
        if resp.status_code != 200:
            logger.error("GET %s -> %s: %s", path, resp.status_code, resp.text)
            raise StorageError()
        return resp.json()

    async def _post(self, path: str, json: dict) -> Any:
        try:
            resp = await self.http.post(f"{self.base_url}{path}", json=json, headers=sign_request({}))
        except httpx.RequestError as e:
            logger.error("POST %s unreachable: %s", path, e)
            raise StorageUnreachable()

        if resp.status_code == 404:
            raise NotFound()
        if resp.status_code != 200:
            logger.error("POST %s -> %s: %s", path, resp.status_code, resp.text)
            raise StorageError()
        return resp.json()