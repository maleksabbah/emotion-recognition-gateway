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
from app.Repositories.RedisRepository import RedisRepository
from app.Repositories.StorageClient import StorageClient


class FileProxyService:
    def __init__(
        self,
        orchestrator: OrchestratorClient,
        storage: StorageClient,
        redis_repo: RedisRepository,
    ):
        self.orchestrator = orchestrator
        self.storage = storage
        self.redis_repo = redis_repo

    # ══════════════════════════════════════════
    # Upload — create session + presign PUT
    # ══════════════════════════════════════════

    async def presign_upload(self, req: UploadRequest, user: User) -> UploadResponse:
        """
        1. Orchestrator: create a session with the correct mode (photo/video).
        2. Storage: pre-register the file row + sign a PUT URL.
        3. Return both — browser uses the URL, polls status with session_id.
        """
        mode = "photo" if req.content_type.startswith("image/") else "video"

        session = await self.orchestrator.create_session(
            mode=mode,
            metadata={
                "user_id": str(user.id),
                "filename": req.filename,
                "content_type": req.content_type,
            },
        )
        # Orchestrator returns JobResponse with key "id" (not "session_id").
        session_id = session["id"]

        presign = await self.storage.presign_upload(
            session_id=session_id,
            file_type="source",
            mime_type=req.content_type,
            original_filename=req.filename,
            user_id=str(user.id),
        )

        s3_key = presign["s3_key"]

        # Store expected s3_key so complete_upload can validate it
        try:
            await self.redis_repo.store_expected_s3_key(session_id, s3_key)
        except Exception:
            pass  # Fail open — don't block uploads if Redis is down

        return UploadResponse(
            session_id=session_id,
            upload_url=presign["upload_url"],
            s3_key=s3_key,
        )

    # ══════════════════════════════════════════
    # Download — find burned file + presign GET
    # ══════════════════════════════════════════

    async def get_download(self, session_id: str, user: User) -> DownloadResponse:
        """
        Resolve the burned output for a session.

        Verifies ownership via orchestrator (user_id in session metadata)
        before returning the presigned download URL.
        """
        # Ownership check — orchestrator returns 404 if user_id doesn't match
        await self.orchestrator.get_session_status(session_id, user_id=str(user.id))

        files = await self.storage.list_files(
            session_id=session_id,
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