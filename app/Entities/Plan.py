"""
Plan entity — maps to gateway_db.plans.

One row per plan (free, pro, ...). This table is the source of truth for
limits: QuotaService reads it on every check and the gateway copies the
live-mode numbers into each access token for the orchestrator.

Rows are seeded on boot from the defaults in app.Config.PLANS when missing;
after that, edit the row to change a plan (no redeploy needed). The `None`
convention for "unlimited" isn't used here — admins bypass limits instead.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.Entities.Base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Plan(Base):
    __tablename__ = "plans"

    name: Mapped[str] = mapped_column(String(32), primary_key=True)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Display price; no billing is wired up yet. 0 = free.
    price_cents_monthly: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd")

    photos_per_month: Mapped[int] = mapped_column(Integer, nullable=False)
    videos_per_month: Mapped[int] = mapped_column(Integer, nullable=False)
    max_image_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_video_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_video_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    uploads_per_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    max_concurrent_jobs: Mapped[int] = mapped_column(Integer, nullable=False)
    live_minutes_per_month: Mapped[int] = mapped_column(Integer, nullable=False)
    live_session_max_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
