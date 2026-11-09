"""The single organisation record."""

import uuid

from sqlalchemy import CheckConstraint, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin

ORGANISATION_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class Organisation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Exactly one row exists; the fixed primary key enforces that at the database level."""

    __tablename__ = "organisation"
    __table_args__ = (
        CheckConstraint(
            f"id = '{ORGANISATION_ID}'::uuid",
            name="singleton",
        ),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(String(120))
    locations: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="UTC", server_default="UTC"
    )
    extra_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
