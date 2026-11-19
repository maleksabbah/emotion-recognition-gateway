"""
Quota routes — plans and the caller's usage against them.

  GET /plans         public — every plan and its limits
  GET /auth/quota    auth   — the caller's plan, limits and this month's usage

/auth/quota sits under /auth/* next to /auth/me for the frontend's contract.
"""
from fastapi import APIRouter, Depends

from app.Dtos.QuotaDto.PlansResponse import PlansResponse
from app.Dtos.QuotaDto.QuotaResponse import QuotaResponse
from app.Entities.User import User
from app.Services.QuotaService import QuotaService
from app.Dependencies import enforce_rate_limit, get_current_user, get_quota_service

router = APIRouter(tags=["quota"])


@router.get(
    "/plans",
    response_model=PlansResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def list_plans() -> PlansResponse:
    return QuotaService.list_plans()


@router.get("/auth/quota", response_model=QuotaResponse)
async def get_quota(
    current_user: User = Depends(get_current_user),
    quota: QuotaService = Depends(get_quota_service),
) -> QuotaResponse:
    return await quota.status(current_user)
