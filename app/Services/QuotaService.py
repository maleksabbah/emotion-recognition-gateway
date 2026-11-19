"""
QuotaService — plan-based usage limits.

Limits  = the user's row in the plans table (PlanRepository; unknown plan →
          free, missing row → code defaults in app.Config.PLANS).
Usage   = the orchestrator's session rows (source of truth): photo/video
          jobs this UTC calendar month, live seconds this month, and jobs
          currently processing. Nothing is counted here, so nothing drifts
          and the monthly reset is just the orchestrator's date filter.
Admins  = users.is_admin → unlimited on everything.

Where it's enforced:
  presign   size vs plan max, uploads per hour (Redis), monthly count.
            Fails OPEN: if Redis or the orchestrator is down the check is
            skipped — nothing is spent until complete.
  complete  monthly count + concurrent jobs, re-checked from fresh usage.
            Fails CLOSED (503) — this is the step that spends compute.
  live      enforced by the orchestrator on its own WebSocket using the
            live limits the gateway puts in the access token (AuthService).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

from app.Config import PLAN_LIMIT_FIELDS
from app.Dtos.QuotaDto.PlanLimits import PlanLimits
from app.Dtos.QuotaDto.PlansResponse import PlanInfo, PlansResponse
from app.Dtos.QuotaDto.QuotaResponse import QuotaResponse, QuotaUsage
from app.Entities.User import User
from app.Exceptions import (
    ConcurrentLimit,
    FileTooLarge,
    QuotaExceeded,
    UploadRateLimited,
    UsageUnavailable,
)
from app.Repositories.OrchestratorClient import OrchestratorClient
from app.Repositories.PlanRepository import PlanRepository
from app.Repositories.RedisRepository import RedisRepository

logger = logging.getLogger("gateway.quota")

Kind = Literal["photo", "video"]

UPLOAD_WINDOW_SECONDS = 3600


# ── period helpers ─────────────────────────────────────

def period() -> tuple[datetime, datetime]:
    """Current UTC calendar month: (start, start of next month)."""
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return start, end


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _reset_date(end: datetime) -> str:
    return f"{end:%B} {end.day}"


def _mb(n: int) -> str:
    value = n / (1024 * 1024)
    return f"{value:.0f} MB" if value >= 10 or value == int(value) else f"{value:.1f} MB"


class QuotaService:
    def __init__(
        self,
        orchestrator: OrchestratorClient,
        redis_repo: RedisRepository,
        plans: PlanRepository,
    ):
        self.orchestrator = orchestrator
        self.redis_repo = redis_repo
        self.plans = plans

    # ══════════════════════════════════════════
    # Plans + limits
    # ══════════════════════════════════════════

    async def list_plans(self) -> PlansResponse:
        return PlansResponse(plans=[PlanInfo(**p) for p in await self.plans.all()])

    @staticmethod
    def is_unlimited(user: User) -> bool:
        return bool(user.is_admin)

    async def limits(self, user: User) -> Optional[dict[str, int]]:
        """The user's plan limits from the plans table, or None if unlimited (admin)."""
        if self.is_unlimited(user):
            return None
        plan = await self.plans.get(user.plan)
        return {field: plan[field] for field in PLAN_LIMIT_FIELDS}

    async def max_bytes(self, user: User, kind: Kind) -> Optional[int]:
        lim = await self.limits(user)
        if lim is None:
            return None
        return lim["max_image_bytes"] if kind == "photo" else lim["max_video_bytes"]

    # ══════════════════════════════════════════
    # Usage (orchestrator)
    # ══════════════════════════════════════════

    async def usage(self, user: User) -> Optional[dict[str, int]]:
        """
        {photos, videos, live_seconds, active_jobs} for this UTC month, or
        None if the orchestrator couldn't be asked. Callers decide whether
        None means allow (read-only checks) or refuse (complete).
        """
        lim = await self.limits(user)
        cap = lim["live_session_max_seconds"] if lim else None
        try:
            body = await self.orchestrator.get_usage(
                str(user.id), live_session_cap_seconds=cap
            )
        except Exception as e:  # unreachable, non-200, bad JSON
            logger.warning("Usage lookup for user %s failed: %s", user.id, e)
            return None
        if not isinstance(body, dict):
            logger.warning("Usage lookup for user %s returned %r", user.id, body)
            return None
        try:
            return {
                "photos": int(body.get("photos") or 0),
                "videos": int(body.get("videos") or 0),
                "live_seconds": int(body.get("live_seconds") or 0),
                "active_jobs": int(body.get("active_jobs") or 0),
            }
        except (TypeError, ValueError):
            logger.warning("Usage lookup for user %s returned bad values: %r", user.id, body)
            return None

    # ══════════════════════════════════════════
    # GET /auth/quota
    # ══════════════════════════════════════════

    async def status(self, user: User) -> QuotaResponse:
        start, end = period()
        plan = await self.plans.get(user.plan)
        lim = None if self.is_unlimited(user) else {f: plan[f] for f in PLAN_LIMIT_FIELDS}
        usage = await self.usage(user)
        return QuotaResponse(
            plan=plan["name"],
            unlimited=lim is None,
            limits=PlanLimits(**(lim or {})),
            usage=QuotaUsage(**(usage or {})),
            usage_available=usage is not None,
            period_start=_iso(start),
            resets_at=_iso(end),
        )

    # ══════════════════════════════════════════
    # Enforcement
    # ══════════════════════════════════════════

    async def check_presign(self, user: User, kind: Kind, size: int) -> None:
        """
        Size, hourly upload rate, monthly count. Fails open on Redis /
        orchestrator errors — complete is the authoritative check.
        """
        lim = await self.limits(user)
        if lim is None:
            return

        max_bytes = lim["max_image_bytes"] if kind == "photo" else lim["max_video_bytes"]
        if size > max_bytes:
            raise self.file_too_large(kind, size, max_bytes)

        await self._check_upload_rate(user, lim["uploads_per_hour"])

        usage = await self.usage(user)
        if usage is not None:
            self._check_monthly(kind, usage, lim)

    async def check_submit(self, user: User, kind: Kind) -> Optional[dict[str, Any]]:
        """
        Re-check monthly count + concurrent jobs from fresh usage. Fails
        CLOSED. Returns the limits dict to forward to the orchestrator
        (None for admins = unlimited).
        """
        lim = await self.limits(user)
        if lim is None:
            return None

        usage = await self.usage(user)
        if usage is None:
            raise UsageUnavailable()

        max_jobs = lim["max_concurrent_jobs"]
        if usage["active_jobs"] >= max_jobs:
            raise ConcurrentLimit(
                f"Your plan allows {max_jobs} {'analyses' if max_jobs != 1 else 'analysis'} "
                "at a time. Wait for the running one to finish, then try again."
            )

        self._check_monthly(kind, usage, lim)
        return {"max_video_seconds": lim["max_video_seconds"]}

    @staticmethod
    def file_too_large(kind: Kind, size: int, max_bytes: int) -> FileTooLarge:
        noun = "photo" if kind == "photo" else "video"
        return FileTooLarge(
            f"This {noun} is {_mb(size)}; your plan allows {noun}s up to {_mb(max_bytes)}.",
            max_bytes=max_bytes,
        )

    # ══════════════════════════════════════════
    # Internal
    # ══════════════════════════════════════════

    @staticmethod
    def _check_monthly(kind: Kind, usage: dict[str, int], lim: dict[str, int]) -> None:
        if kind == "photo":
            used, allowed, noun = usage["photos"], lim["photos_per_month"], "photo"
        else:
            used, allowed, noun = usage["videos"], lim["videos_per_month"], "video"
        if used >= allowed:
            _, end = period()
            raise QuotaExceeded(
                f"You've used all {allowed} {noun} uploads for this month. "
                f"Your limit resets on {_reset_date(end)}.",
                resets_at=_iso(end),
            )

    async def _check_upload_rate(self, user: User, per_hour: int) -> None:
        """Fixed hourly window per user. Redis down = allow."""
        now = int(time.time())
        bucket = now // UPLOAD_WINDOW_SECONDS
        key = RedisRepository.upload_rate_key(str(user.id), bucket)
        try:
            count = await self.redis_repo.incr_with_expiry(key, UPLOAD_WINDOW_SECONDS)
        except Exception as e:
            logger.error("Upload rate check failed (allowing request): %s", e)
            return
        if count > per_hour:
            retry_after = UPLOAD_WINDOW_SECONDS - (now % UPLOAD_WINDOW_SECONDS)
            raise UploadRateLimited(
                f"You've reached your plan's limit of {per_hour} uploads per hour. "
                f"Try again in {max(1, -(-retry_after // 60))} minutes.",
                retry_after=retry_after,
            )
