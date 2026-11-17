"""
JobProxyService — gateway's job/session domain.

Pure proxy to orchestrator. Owns:
  - complete_upload: signal that the upload finished; orchestrator publishes media_tasks
  - list_jobs:       all jobs/sessions for the user (orchestrator already scopes)
  - get_status:      progress for one job
  - end_session:     used by WS disconnect cleanup

Pure DI: takes only OrchestratorClient. The session-create call lives in
FileProxyService.presign_upload because it's part of the upload flow.
"""
from __future__ import annotations

import logging

from app.Dtos.JobDto.JobResponse import JobResponse
from app.Dtos.JobDto.JobStatusResponse import JobStatusResponse
from app.Dtos.UploadDto.UploadCompleteRequest import UploadCompleteRequest
from app.Dtos.UploadDto.UploadCompleteResponse import UploadCompleteResponse
from app.Entities.User import User
from app.Exceptions import Forbidden
from app.Repositories.OrchestratorClient import OrchestratorClient
from app.Repositories.RedisRepository import RedisRepository

logger = logging.getLogger("gateway.job-proxy")


class JobProxyService:
    def __init__(self, orchestrator: OrchestratorClient, redis_repo: RedisRepository):
        self.orchestrator = orchestrator
        self.redis_repo = redis_repo

    # ══════════════════════════════════════════
    # Lifecycle
    # ══════════════════════════════════════════

    async def complete_upload(
        self, req: UploadCompleteRequest, user: User
    ) -> UploadCompleteResponse:
        # Validate s3_key matches what was issued during presign
        try:
            expected = await self.redis_repo.get_expected_s3_key(req.session_id)
            if expected is not None and expected != req.s3_key:
                logger.warning(
                    "s3_key mismatch for session %s: expected=%s got=%s",
                    req.session_id, expected, req.s3_key,
                )
                raise Forbidden("Invalid s3_key")
        except Forbidden:
            raise
        except Exception:
            pass  # Fail open on Redis errors

        data = await self.orchestrator.submit_upload_job(
            session_id=req.session_id,
            mode=req.mode or "video",
            s3_key=req.s3_key,
        )
        return UploadCompleteResponse(
            status=data.get("status", "queued"),
            session_id=data.get("session_id", req.session_id),
        )

    async def end_session(self, session_id: str) -> None:
        """Best-effort. Used by WS disconnect cleanup."""
        await self.orchestrator.end_session(session_id)

    # ══════════════════════════════════════════
    # Reads
    # ══════════════════════════════════════════

    async def list_jobs(self, user: User) -> list[JobResponse]:
        rows = await self.orchestrator.list_sessions(user_id=str(user.id))
        return [JobResponse.model_validate(row) for row in rows]

    async def get_status(self, session_id: str, user: User) -> JobStatusResponse:
        data = await self.orchestrator.get_session_status(session_id, user_id=str(user.id))
        return JobStatusResponse.model_validate(data)