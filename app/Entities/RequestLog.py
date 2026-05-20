"""
RequestLog entity — maps to gateway_db.request_logs.

Write-only audit trail. Populated by RequestLoggingMiddleware on every request.
No FK to users (logs survive account deletion). Indexed for time-range queries
and path/IP forensics.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Double, Integer, String, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.Entities.Base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RequestLog(Base):
    __tablename__ = "request_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    method: Mapped[str] = mapped_column(String(8), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_time_ms: Mapped[float] = mapped_column(Double, nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        Index("idx_request_logs_user", "user_id"),
        Index("idx_request_logs_created", "created_at"),
        Index("idx_request_logs_path", "path"),
    )

    def __repr__(self) -> str:
        return f"<RequestLog {self.method} {self.path} {self.status_code}>"