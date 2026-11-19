"""
JobProxyService — gateway's job/session domain.

Pure proxy to orchestrator. Owns:
  - complete_upload: signal that the upload finished; orchestrator publishes media_tasks
  - list_jobs:       all jobs/sessions for the user (orchestrator already scopes)
  - get_status:      progress for one job
  - end_session:     used by WS disconnect cleanup

Pure DI: OrchestratorClient, RedisRepository, StorageClient, QuotaService.
The session-create call lives in FileProxyService.presign_upload because
it's part of the upload flow.
"""
from __future__ import annotations

import asyncio
import logging
import secrets

from app.Dtos.JobDto.JobResponse import JobResponse
from app.Dtos.JobDto.JobStatusResponse import JobStatusResponse
from app.Dtos.UploadDto.UploadCompleteRequest import UploadCompleteRequest
from app.Dtos.UploadDto.UploadCompleteResponse import UploadCompleteResponse
from app.Entities.User import User
from app.Exceptions import (
    ConcurrentLimit,
    Forbidden,
    NotFound,
    StorageError,
    UploadExpired,
    UsageUnavailable,
)
from app.Repositories.OrchestratorClient import OrchestratorClient
from app.Repositories.RedisRepository import RedisRepository
from app.Repositories.StorageClient import StorageClient
from app.Services.QuotaService import QuotaService

logger = logging.getLogger("gateway.job-proxy")

# Per-user lock around check+submit so parallel completes can't both pass
# the monthly / concurrent check before either is recorded.
_COMPLETE_LOCK_TTL_SECONDS = 15
_COMPLETE_LOCK_WAIT_SECONDS = 5.0
_COMPLETE_LOCK_POLL_SECONDS = 0.25
# After a successful submit the lock lingers briefly instead of being
# deleted, covering the gap before the orchestrator's commit is visible.
_COMPLETE_LOCK_LINGER_MS = 2000


class JobProxyService:
    def __init__(
        self,
        orchestrator: OrchestratorClient,
        redis_repo: RedisRepository,
        storage: StorageClient,
        quota: QuotaService,
    ):
        self.orchestrator = orchestrator
        self.redis_repo = redis_repo
        self.storage = storage
        self.quota = quota

    # ══════════════════════════════════════════
    # Lifecycle
    # ══════════════════════════════════════════

    async def complete_upload(
        self, req: UploadCompleteRequest, user: User
    ) -> UploadCompleteResponse:
        """
        Fails CLOSED — this is the step that spends compute.

          1. The presign entry must exist and match (s3_key + owner).
          2. Under a per-user lock: re-check monthly count + concurrent
             jobs from fresh orchestrator usage (503 if unavailable).
          3. HEAD the uploaded object; reject + delete it if over the limit.
          4. Submit with the server-side mode and the plan's video limit.
        """
        try:
            entry = await self.redis_repo.get_upload_entry(req.session_id)
        except Exception as e:
            logger.error("get_upload_entry failed for %s: %s", req.session_id, e)
            raise UsageUnavailable(
                "We couldn't verify your upload right now. Please try again in a minute."
            )
        if entry is None:
            raise UploadExpired()
        if entry.get("s3_key") != req.s3_key or entry.get("user_id") != str(user.id):
            logger.warning(
                "upload entry mismatch for session %s: expected=%s got=%s (user %s)",
                req.session_id, entry.get("s3_key"), req.s3_key, user.id,
            )
            raise Forbidden("Invalid s3_key")
        kind = entry.get("kind")
        if kind not in ("photo", "video"):
            raise UploadExpired()

        lock_name = f"upload-complete:{user.id}"
        token = secrets.token_hex(16)
        await self._acquire_complete_lock(lock_name, token)

        submitted = False
        try:
            limits = await self.quota.check_submit(user, kind)
            await self._check_uploaded_size(req.session_id, req.s3_key, user, kind)

            data = await self.orchestrator.submit_upload_job(
                session_id=req.session_id,
                mode=kind,
                s3_key=req.s3_key,
                limits=limits,
            )
            submitted = True

            # One submit per presign — a replayed complete gets upload_expired.
            try:
                await self.redis_repo.delete_upload_entry(req.session_id)
            except Exception as e:
                logger.warning("delete_upload_entry failed for %s: %s", req.session_id, e)
        finally:
            try:
                if submitted:
                    await self.redis_repo.shorten_lock(
                        lock_name, token, _COMPLETE_LOCK_LINGER_MS
                    )
                else:
                    await self.redis_repo.release_lock(lock_name, token)
            except Exception as e:
                logger.warning("complete lock cleanup failed for %s: %s", user.id, e)

        return UploadCompleteResponse(
            status=data.get("status", "queued"),
            session_id=data.get("session_id", req.session_id),
        )

    async def _acquire_complete_lock(self, lock_name: str, token: str) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + _COMPLETE_LOCK_WAIT_SECONDS
        while True:
            try:
                if await self.redis_repo.acquire_lock(
                    lock_name, token, _COMPLETE_LOCK_TTL_SECONDS
                ):
                    return
            except Exception as e:
                logger.error("acquire_lock failed for %s: %s", lock_name, e)
                raise UsageUnavailable(
                    "We couldn't start your upload right now. Please try again in a minute."
                )
            if loop.time() >= deadline:
                raise ConcurrentLimit(
                    "Another upload of yours is being started. "
                    "Please try again in a few seconds.",
                    retry_after=5,
                )
            await asyncio.sleep(_COMPLETE_LOCK_POLL_SECONDS)

    async def _check_uploaded_size(
        self, session_id: str, s3_key: str, user: User, kind: str
    ) -> None:
        """HEAD the real object. Missing → upload_expired; too big → 413 + delete."""
        try:
            info = await self.storage.head_source(session_id)
        except NotFound:
            raise UploadExpired("Upload not found, please upload again")

        if info.get("s3_key") != s3_key:
            logger.warning(
                "source key mismatch for session %s: storage=%s client=%s",
                session_id, info.get("s3_key"), s3_key,
            )
            raise Forbidden("Invalid s3_key")

        actual = info.get("size_bytes")
        if not isinstance(actual, int):
            logger.error("head_source for %s returned no size: %r", session_id, info)
            raise StorageError()

        max_bytes = await self.quota.max_bytes(user, kind)
        if max_bytes is None or actual <= max_bytes:
            return

        logger.warning(
            "Uploaded object for %s is %d bytes, over plan max %d — deleting",
            session_id, actual, max_bytes,
        )
        try:
            await self.storage.delete_source(session_id)
        except Exception as e:
            logger.error("delete_source failed for %s: %s", session_id, e)
        try:
            await self.redis_repo.delete_upload_entry(session_id)
        except Exception as e:
            logger.warning("delete_upload_entry failed for %s: %s", session_id, e)
        raise self.quota.file_too_large(kind, actual, max_bytes)

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