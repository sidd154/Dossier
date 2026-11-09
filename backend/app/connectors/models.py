"""External integration configuration and encrypted credentials."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    LargeBinary,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class ConnectorType(enum.StrEnum):
    GOOGLE_SHEETS = "GOOGLE_SHEETS"
    ZOHO_CRM = "ZOHO_CRM"


def _enum_values(enum_type: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_type]


class Connector(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An integration instance. Multiple connectors of the same type are allowed."""

    __tablename__ = "connector"

    name: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    type: Mapped[ConnectorType] = mapped_column(
        SAEnum(ConnectorType, name="connector_type", values_callable=_enum_values),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    # Non-secret settings only: spreadsheet id, module name, API domain, etc.
    config: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_validation_error: Mapped[str | None] = mapped_column(Text)

    credential: Mapped["ConnectorCredential | None"] = relationship(
        back_populates="connector",
        lazy="raise",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ConnectorCredential(UUIDPrimaryKeyMixin, Base):
    """Encrypted secret payload. Exactly one per connector."""

    __tablename__ = "connector_credential"

    connector_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connector.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    key_id: Mapped[str] = mapped_column(String(32), nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=text("now()")
    )
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    connector: Mapped[Connector] = relationship(
        back_populates="credential", lazy="raise"
    )
