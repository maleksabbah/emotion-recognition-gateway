"""
FileProxyService — gateway's file domain.

Owns the upload flow end-to-end:
  - presign_upload: creates a session via orchestrator + asks storage to
    presign a PUT URL. Single round-trip from the controller's POV.
  - get_download:   asks storage for the burned file and presigns a GET URL.

Takes both OrchestratorClient and StorageClient because the upload flow
needs orchestrator (sessions) and storage (presigning) coordinated. The
controller doesn't see this — it calls one method.
"""
from __future__ import annotations

from app.Dtos.JobDto.DownloadResponse import DownloadResponse
from app.Dtos.UploadDto.UploadRequest import UploadRequest
from app.Dtos.UploadDto.UploadResponse import UploadResponse
from app.Entities.User import User
from app.Exceptions import NotFound
from app.Repositories.OrchestratorClient import OrchestratorClient
from app.Repositories.StorageClient import StorageClient


class FileProxyService:
    def __init__(self, orchestrator: OrchestratorClient, storage: StorageClient):
        self.orchestrator = orchestrator
        self.storage = storage

    # ══════════════════════════════════════════
    # Upload — create session + presign PUT
    # ══════════════════════════════════════════

    async def presign_upload(self, req: UploadRequest, user: User) -> UploadResponse:
        """
        1. Orchestrator: create a session with the user's chosen mode.
        2. Storage: pre-register the file row + sign a PUT URL.
        3. Return both — browser uses the URL, polls status with session_id.
        """
        session = await self.orchestrator.create_session(
            mode=req.mode,
            metadata={
                "user_id": str(user.id),
                "filename": req.filename,
                "content_type": req.content_type,
            },
        )
        session_id = session["session_id"]

        presign = await self.storage.presign_upload(
            session_id=session_id,
            file_type="source",
            mime_type=req.content_type,
            original_filename=req.filename,
            user_id=str(user.id),
        )

        return UploadResponse(
            session_id=session_id,
            upload_url=presign["upload_url"],
            s3_key=presign["s3_key"],
        )

    # ══════════════════════════════════════════
    # Download — find burned file + presign GET
    # ══════════════════════════════════════════

    async def get_download(self, session_id: str, user: User) -> DownloadResponse:
        """
        Resolve the burned output for a session. Scoped to user_id at the
        storage query so a session_id alone won't reveal another user's file.
        """
        files = await self.storage.list_files(
            session_id=session_id,
            user_id=str(user.id),
            category="burned",
        )
        if not files:
            raise NotFound()

        record = files[0]
        presign = await self.storage.presign_download(record["id"])
        filename = record["s3_key"].rsplit("/", 1)[-1]

        return DownloadResponse(
            download_url=presign["download_url"],
            filename=filename,
        )