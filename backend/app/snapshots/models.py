"""Immutable daily snapshots of a data source."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.mixins import UUIDPrimaryKeyMixin, utcnow


class SnapshotStatus(enum.StrEnum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


def _enum_values(enum_type: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_type]


class Snapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "snapshot"
    __table_args__ = (
        Index("ix_snapshot_source_captured", "data_source_id", "captured_at"),
    )

    data_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_source.id", ondelete="CASCADE"), nullable=False, index=True
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=text("now()")
    )
    status: Mapped[SnapshotStatus] = mapped_column(
        SAEnum(SnapshotStatus, name="snapshot_status", values_callable=_enum_values),
        nullable=False,
        default=SnapshotStatus.READY,
        server_default=SnapshotStatus.READY.value,
    )
    record_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    schema_hash: Mapped[str | None] = mapped_column(String(64))
    source_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )


class SnapshotRecord(Base):
    __tablename__ = "snapshot_record"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "row_index", name="uq_snapshot_record_row"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("snapshot.id", ondelete="CASCADE"), nullable=False, index=True
    )
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255))
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
