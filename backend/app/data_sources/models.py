"""Usable sources exposed by a connector, and department grants over them.

Permissions attach to a data source, never to a connector. This is what makes
"Sales may read the Sales sheet but not the HR sheet" expressible.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.connectors.models import Connector
from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utcnow
from app.snapshots.models import Snapshot


class DataSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "data_source"
    __table_args__ = (
        UniqueConstraint(
            "connector_id", "external_id", name="uq_data_source_connector_external"
        ),
    )

    connector_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connector.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Identifier used by the external system: a sheet tab reference or CRM module.
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    schema_hash: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    # The snapshot retrieval and mail read from. Only ever updated after a fully
    # persisted snapshot, so a failed sync cannot disturb it.
    current_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "snapshot.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_data_source_current_snapshot_id_snapshot",
        ),
    )

    connector: Mapped[Connector] = relationship(lazy="raise")
    current_snapshot: Mapped[Snapshot | None] = relationship(
        lazy="raise", foreign_keys=[current_snapshot_id]
    )


class DataSourcePermission(Base):
    """A department's grant over one source. Absence means no access."""

    __tablename__ = "data_source_permission"

    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("department.id", ondelete="CASCADE"), primary_key=True
    )
    # Indexed separately from the primary key: cascading deletes and "who can read
    # this source" queries both look up by source id alone.
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_source.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=text("now()")
    )
