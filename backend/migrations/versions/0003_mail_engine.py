"""Mail settings, templates, schedules, executions, deliveries.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MAIL_SETTINGS_ID = "00000000-0000-0000-0000-000000000002"


def upgrade() -> None:
    smtp_security = postgresql.ENUM(
        "NONE", "STARTTLS", "SSL", name="smtp_security", create_type=False
    )
    mail_frequency = postgresql.ENUM(
        "DAILY", "WEEKLY", "MONTHLY", name="mail_frequency", create_type=False
    )
    mail_trigger = postgresql.ENUM(
        "SCHEDULED", "MANUAL", name="mail_trigger", create_type=False
    )
    mail_execution_status = postgresql.ENUM(
        "RUNNING",
        "SUCCEEDED",
        "PARTIAL",
        "FAILED",
        "SKIPPED",
        name="mail_execution_status",
        create_type=False,
    )
    mail_delivery_status = postgresql.ENUM(
        "SENT", "FAILED", "SKIPPED", name="mail_delivery_status", create_type=False
    )
    for enum_type in (
        smtp_security,
        mail_frequency,
        mail_trigger,
        mail_execution_status,
        mail_delivery_status,
    ):
        enum_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "mail_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("key_id", sa.String(length=32), nullable=True),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("from_email", postgresql.CITEXT(), nullable=False),
        sa.Column("from_name", sa.String(length=200), nullable=True),
        sa.Column(
            "security", smtp_security, server_default="STARTTLS", nullable=False
        ),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"id = '{MAIL_SETTINGS_ID}'::uuid", name="ck_mail_settings_singleton"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_mail_settings"),
    )

    op.create_table(
        "mail_template",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", postgresql.CITEXT(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("subject_template", sa.String(length=500), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_mail_template"),
        sa.UniqueConstraint("name", name="uq_mail_template_name"),
    )

    op.create_table(
        "mail_schedule",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", postgresql.CITEXT(), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("frequency", mail_frequency, nullable=False),
        sa.Column("time_of_day", sa.Time(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=True),
        sa.Column("day_of_month", sa.SmallInteger(), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("row_limit", sa.Integer(), server_default=sa.text("50"), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["mail_template.id"],
            name="fk_mail_schedule_template_id_mail_template",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_mail_schedule"),
        sa.UniqueConstraint("name", name="uq_mail_schedule_name"),
    )
    op.create_index("ix_mail_schedule_template_id", "mail_schedule", ["template_id"])
    op.create_index("ix_mail_schedule_next_run", "mail_schedule", ["next_run_at"])

    op.create_table(
        "mail_schedule_source",
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("data_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["mail_schedule.id"],
            name="fk_mail_schedule_source_schedule_id_mail_schedule",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["data_source_id"],
            ["data_source.id"],
            name="fk_mail_schedule_source_data_source_id_data_source",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "schedule_id", "data_source_id", name="pk_mail_schedule_source"
        ),
    )
    op.create_index(
        "ix_mail_schedule_source_data_source_id",
        "mail_schedule_source",
        ["data_source_id"],
    )

    op.create_table(
        "mail_schedule_department",
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["mail_schedule.id"],
            name="fk_mail_schedule_department_schedule_id_mail_schedule",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["department.id"],
            name="fk_mail_schedule_department_department_id_department",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "schedule_id", "department_id", name="pk_mail_schedule_department"
        ),
    )
    op.create_index(
        "ix_mail_schedule_department_department_id",
        "mail_schedule_department",
        ["department_id"],
    )

    op.create_table(
        "mail_schedule_user",
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["mail_schedule.id"],
            name="fk_mail_schedule_user_schedule_id_mail_schedule",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name="fk_mail_schedule_user_user_id_app_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("schedule_id", "user_id", name="pk_mail_schedule_user"),
    )
    op.create_index("ix_mail_schedule_user_user_id", "mail_schedule_user", ["user_id"])

    op.create_table(
        "mail_execution",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trigger", mail_trigger, nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status", mail_execution_status, server_default="RUNNING", nullable=False
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recipient_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("sent_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("skipped_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["mail_schedule.id"],
            name="fk_mail_execution_schedule_id_mail_schedule",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_mail_execution"),
        sa.UniqueConstraint(
            "schedule_id", "scheduled_for", "trigger", name="uq_mail_execution_slot"
        ),
    )
    op.create_index("ix_mail_execution_schedule_id", "mail_execution", ["schedule_id"])
    op.create_index(
        "ix_mail_execution_schedule_started",
        "mail_execution",
        ["schedule_id", "started_at"],
    )

    op.create_table(
        "mail_delivery",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", mail_delivery_status, nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("message_id", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["mail_execution.id"],
            name="fk_mail_delivery_execution_id_mail_execution",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"],
            ["app_user.id"],
            name="fk_mail_delivery_recipient_user_id_app_user",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["department.id"],
            name="fk_mail_delivery_department_id_department",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_mail_delivery"),
        sa.UniqueConstraint(
            "execution_id", "email", name="uq_mail_delivery_recipient"
        ),
    )
    op.create_index("ix_mail_delivery_execution_id", "mail_delivery", ["execution_id"])


def downgrade() -> None:
    op.drop_table("mail_delivery")
    op.drop_table("mail_execution")
    op.drop_table("mail_schedule_user")
    op.drop_table("mail_schedule_department")
    op.drop_table("mail_schedule_source")
    op.drop_table("mail_schedule")
    op.drop_table("mail_template")
    op.drop_table("mail_settings")

    for name in (
        "mail_delivery_status",
        "mail_execution_status",
        "mail_trigger",
        "mail_frequency",
        "smtp_security",
    ):
        postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)
