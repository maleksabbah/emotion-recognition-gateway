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

from app.Dtos.JobDto.JobResponse import JobResponse
from app.Dtos.JobDto.JobStatusResponse import JobStatusResponse
from app.Dtos.UploadDto.UploadCompleteRequest import UploadCompleteRequest
from app.Dtos.UploadDto.UploadCompleteResponse import UploadCompleteResponse
from app.Entities.User import User
from app.Repositories.OrchestratorClient import OrchestratorClient


class JobProxyService:
    def __init__(self, orchestrator: OrchestratorClient):
        self.orchestrator = orchestrator

    # ══════════════════════════════════════════
    # Lifecycle
    # ══════════════════════════════════════════

    async def complete_upload(
        self, req: UploadCompleteRequest, user: User
    ) -> UploadCompleteResponse:
        # Frontend posts the REAL s3_key it got from /upload/request — use it.
        # Hardcoding a directory prefix here was crashing media-worker on S3 GET.
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
        rows = await self.orchestrator.list_sessions()
        return [JobResponse.model_validate(row) for row in rows]

    async def get_status(self, session_id: str, user: User) -> JobStatusResponse:
        data = await self.orchestrator.get_session_status(session_id)
        return JobStatusResponse.model_validate(data)