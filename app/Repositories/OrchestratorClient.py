"""
OrchestratorClient — gateway → orchestrator HTTP boundary.

Owns the shared httpx.AsyncClient injected from app.state. Services depend
on this class, not on httpx. URL paths live only here.

Methods are limited to what the gateway actually calls:
  - create_session          (FileProxyService.presign_upload)
  - submit_upload_job       (JobProxyService.complete_upload)
  - end_session             (JobProxyService.end_session)
  - get_session_status      (JobProxyService.get_status)
  - list_sessions           (JobProxyService.list_jobs)
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.Config import ORCHESTRATOR_URL
from app.Exceptions import (
    NotFound,
    OrchestratorError,
    OrchestratorUnreachable,
)

logger = logging.getLogger("gateway.orchestrator-client")


class OrchestratorClient:
    def __init__(self, http: httpx.AsyncClient, base_url: str = ORCHESTRATOR_URL):
        self.http = http
        self.base_url = base_url

    # ══════════════════════════════════════════
    # Session operations
    # ══════════════════════════════════════════

    async def create_session(
        self, mode: str, metadata: Optional[dict] = None
    ) -> dict:
        return await self._post(
            "/api/sessions",
            json={"mode": mode, "metadata": metadata or {}},
        )

    async def list_sessions(self) -> list[dict]:
        data = await self._get("/api/sessions")
        return data if isinstance(data, list) else []

    async def get_session_status(self, session_id: str) -> dict:
        return await self._get(f"/api/sessions/{session_id}/status")

    async def end_session(self, session_id: str) -> None:
        """Best-effort. Never raises — WS cleanup must not block."""
        try:
            resp = await self.http.post(
                f"{self.base_url}/api/sessions/{session_id}/end"
            )
            if resp.status_code not in (200, 202):
                logger.warning(
                    "end_session non-OK %s: %s", resp.status_code, resp.text
                )
        except httpx.RequestError as e:
            logger.error("end_session unreachable: %s", e)

    # ══════════════════════════════════════════
    # Upload operations
    # ══════════════════════════════════════════

    async def submit_upload_job(
        self, session_id: str, mode: str, s3_key: str
    ) -> dict:
        return await self._post(
            "/api/upload-job",
            json={"session_id": session_id, "mode": mode, "s3_key": s3_key},
        )

    # ══════════════════════════════════════════
    # Internal HTTP helpers
    # ══════════════════════════════════════════

    async def _get(self, path: str) -> Any:
        try:
            resp = await self.http.get(f"{self.base_url}{path}")
        except httpx.RequestError as e:
            logger.error("GET %s unreachable: %s", path, e)
            raise OrchestratorUnreachable()

        if resp.status_code == 404:
            raise NotFound()
        if resp.status_code != 200:
            logger.error("GET %s -> %s: %s", path, resp.status_code, resp.text)
            raise OrchestratorError()
        return resp.json()

    async def _post(self, path: str, json: dict) -> Any:
        try:
            resp = await self.http.post(f"{self.base_url}{path}", json=json)
        except httpx.RequestError as e:
            logger.error("POST %s unreachable: %s", path, e)
            raise OrchestratorUnreachable()

        if resp.status_code != 200:
            logger.error("POST %s -> %s: %s", path, resp.status_code, resp.text)
            raise OrchestratorError()
        return resp.json()