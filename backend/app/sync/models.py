"""Sync execution records."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.mixins import UUIDPrimaryKeyMixin, utcnow


class SyncStatus(enum.StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class SyncTrigger(enum.StrEnum):
    SCHEDULED = "SCHEDULED"
    MANUAL = "MANUAL"


def _enum_values(enum_type: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_type]


class SyncJob(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "sync_job"
    __table_args__ = (
        Index("ix_sync_job_source_started", "data_source_id", "started_at"),
    )

    data_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_source.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[SyncStatus] = mapped_column(
        SAEnum(SyncStatus, name="sync_status", values_callable=_enum_values),
        nullable=False,
        default=SyncStatus.RUNNING,
        server_default=SyncStatus.RUNNING.value,
    )
    trigger: Mapped[SyncTrigger] = mapped_column(
        SAEnum(SyncTrigger, name="sync_trigger", values_callable=_enum_values),
        nullable=False,
        default=SyncTrigger.SCHEDULED,
        server_default=SyncTrigger.SCHEDULED.value,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=text("now()")
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    record_count: Mapped[int | None] = mapped_column(Integer)
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("snapshot.id", ondelete="SET NULL")
    )
