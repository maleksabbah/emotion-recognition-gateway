"""
Upload routes — the two-step upload flow.

  POST /upload/request    create session + presign MinIO URL
  POST /upload/complete   tell orchestrator the upload is done

Both rate-limited (uploads have stricter limits than the general route).
Both require auth.
"""
from fastapi import APIRouter, Depends

from app.Dtos.UploadDto.UploadRequest import UploadRequest
from app.Dtos.UploadDto.UploadResponse import UploadResponse
from app.Dtos.UploadDto.UploadCompleteRequest import UploadCompleteRequest
from app.Dtos.UploadDto.UploadCompleteResponse import UploadCompleteResponse
from app.Entities.User import User
from app.Services.FileProxyService import FileProxyService
from app.Services.JobProxyService import JobProxyService
from app.Dependencies import (
    enforce_rate_limit,
    get_current_user,
    get_file_proxy_service,
    get_job_proxy_service,
)

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post(
    "/request",
    response_model=UploadResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def request_upload(
    req: UploadRequest,
    current_user: User = Depends(get_current_user),
    files: FileProxyService = Depends(get_file_proxy_service),
) -> UploadResponse:
    return await files.presign_upload(req, current_user)


@router.post(
    "/complete",
    response_model=UploadCompleteResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def complete_upload(
    req: UploadCompleteRequest,
    current_user: User = Depends(get_current_user),
    jobs: JobProxyService = Depends(get_job_proxy_service),
) -> UploadCompleteResponse:
    return await jobs.complete_upload(req, current_user)