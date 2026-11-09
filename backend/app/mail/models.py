"""Mail settings, templates, schedules, executions, and deliveries."""

import enum
import uuid
from datetime import datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Table,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data_sources.models import DataSource
from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utcnow
from app.departments.models import Department

MAIL_SETTINGS_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


class SmtpSecurity(enum.StrEnum):
    NONE = "NONE"
    STARTTLS = "STARTTLS"
    SSL = "SSL"


class MailFrequency(enum.StrEnum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class MailTrigger(enum.StrEnum):
    SCHEDULED = "SCHEDULED"
    MANUAL = "MANUAL"


class MailExecutionStatus(enum.StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class MailDeliveryStatus(enum.StrEnum):
    SENT = "SENT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


def _enum_values(enum_type: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_type]


class MailSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Singleton SMTP configuration. The password is encrypted, never returned."""

    __tablename__ = "mail_settings"
    __table_args__ = (
        CheckConstraint(
            f"id = '{MAIL_SETTINGS_ID}'::uuid", name="singleton"
        ),
    )

    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=587)
    username: Mapped[str | None] = mapped_column(String(255))
    key_id: Mapped[str | None] = mapped_column(String(32))
    ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    from_email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    from_name: Mapped[str | None] = mapped_column(String(200))
    security: Mapped[SmtpSecurity] = mapped_column(
        SAEnum(SmtpSecurity, name="smtp_security", values_callable=_enum_values),
        nullable=False,
        default=SmtpSecurity.STARTTLS,
        server_default=SmtpSecurity.STARTTLS.value,
    )
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_error: Mapped[str | None] = mapped_column(Text)


class MailTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mail_template"

    name: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    subject_template: Mapped[str] = mapped_column(String(500), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )


mail_schedule_sources = Table(
    "mail_schedule_source",
    Base.metadata,
    Column(
        "schedule_id",
        UUID(as_uuid=True),
        ForeignKey("mail_schedule.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "data_source_id",
        UUID(as_uuid=True),
        ForeignKey("data_source.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)

class MailSchedule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mail_schedule"
    __table_args__ = (Index("ix_mail_schedule_next_run", "next_run_at"),)

    name: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mail_template.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("department.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    frequency: Mapped[MailFrequency] = mapped_column(
        SAEnum(MailFrequency, name="mail_frequency", values_callable=_enum_values),
        nullable=False,
    )
    time_of_day: Mapped[time] = mapped_column(Time, nullable=False)
    weekday: Mapped[int | None] = mapped_column(SmallInteger)
    day_of_month: Mapped[int | None] = mapped_column(SmallInteger)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    row_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, default=50, server_default=text("50")
    )
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    template: Mapped[MailTemplate] = relationship(lazy="raise")
    department: Mapped[Department] = relationship(lazy="raise")
    sources: Mapped[list[DataSource]] = relationship(
        secondary=mail_schedule_sources, lazy="raise"
    )


class MailExecution(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "mail_execution"
    __table_args__ = (
        UniqueConstraint(
            "schedule_id",
            "scheduled_for",
            "trigger",
            name="uq_mail_execution_slot",
        ),
        Index("ix_mail_execution_schedule_started", "schedule_id", "started_at"),
    )

    schedule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mail_schedule.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trigger: Mapped[MailTrigger] = mapped_column(
        SAEnum(MailTrigger, name="mail_trigger", values_callable=_enum_values),
        nullable=False,
    )
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[MailExecutionStatus] = mapped_column(
        SAEnum(
            MailExecutionStatus, name="mail_execution_status", values_callable=_enum_values
        ),
        nullable=False,
        default=MailExecutionStatus.RUNNING,
        server_default=MailExecutionStatus.RUNNING.value,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=text("now()")
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recipient_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    sent_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    failed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    skipped_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    error: Mapped[str | None] = mapped_column(Text)


class MailDelivery(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "mail_delivery"
    __table_args__ = (
        UniqueConstraint("execution_id", "email", name="uq_mail_delivery_recipient"),
    )

    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mail_execution.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recipient_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("department.id", ondelete="SET NULL")
    )
    status: Mapped[MailDeliveryStatus] = mapped_column(
        SAEnum(
            MailDeliveryStatus, name="mail_delivery_status", values_callable=_enum_values
        ),
        nullable=False,
    )
    error: Mapped[str | None] = mapped_column(Text)
    message_id: Mapped[str | None] = mapped_column(String(255))
    subject: Mapped[str | None] = mapped_column(String(500))
    body: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
