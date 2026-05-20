"""
Job routes — read-only job/session queries.

  GET /sessions                       list user's sessions
  GET /sessions/{id}/status           progress for one session
  GET /sessions/{id}/download         presigned download URL for burned output

All require auth. No rate limiting (status polling can be frequent).
"""
from fastapi import APIRouter, Depends

from app.Dtos.JobDto.JobResponse import JobResponse
from app.Dtos.JobDto.JobStatusResponse import JobStatusResponse
from app.Dtos.JobDto.DownloadResponse import DownloadResponse
from app.Entities.User import User
from app.Services.FileProxyService import FileProxyService
from app.Services.JobProxyService import JobProxyService
from app.Dependencies import (
    get_current_user,
    get_file_proxy_service,
    get_job_proxy_service,
)

router = APIRouter(prefix="/sessions", tags=["jobs"])


@router.get("", response_model=list[JobResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    jobs: JobProxyService = Depends(get_job_proxy_service),
) -> list[JobResponse]:
    return await jobs.list_jobs(current_user)


@router.get("/{session_id}/status", response_model=JobStatusResponse)
async def get_status(
    session_id: str,
    current_user: User = Depends(get_current_user),
    jobs: JobProxyService = Depends(get_job_proxy_service),
) -> JobStatusResponse:
    return await jobs.get_status(session_id, current_user)


@router.get("/{session_id}/download", response_model=DownloadResponse)
async def get_download(
    session_id: str,
    current_user: User = Depends(get_current_user),
    files: FileProxyService = Depends(get_file_proxy_service),
) -> DownloadResponse:
    return await files.get_download(session_id, current_user)