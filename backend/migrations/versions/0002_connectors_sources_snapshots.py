"""Connectors, data sources, department grants, sync jobs, snapshots.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connector_type = postgresql.ENUM(
        "GOOGLE_SHEETS", "ZOHO_CRM", name="connector_type", create_type=False
    )
    sync_status = postgresql.ENUM(
        "RUNNING", "SUCCEEDED", "PARTIAL", "FAILED", name="sync_status", create_type=False
    )
    sync_trigger = postgresql.ENUM(
        "SCHEDULED", "MANUAL", name="sync_trigger", create_type=False
    )
    snapshot_status = postgresql.ENUM(
        "READY", "PARTIAL", "FAILED", name="snapshot_status", create_type=False
    )
    for enum_type in (connector_type, sync_status, sync_trigger, snapshot_status):
        enum_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "connector",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", postgresql.CITEXT(), nullable=False),
        sa.Column("type", connector_type, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_validation_error", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_connector"),
        sa.UniqueConstraint("name", name="uq_connector_name"),
    )

    op.create_table(
        "connector_credential",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connector_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key_id", sa.String(length=32), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["connector_id"],
            ["connector.id"],
            name="fk_connector_credential_connector_id_connector",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_connector_credential"),
        sa.UniqueConstraint("connector_id", name="uq_connector_credential_connector_id"),
    )

    op.create_table(
        "data_source",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connector_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("schema_hash", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("current_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
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
            ["connector_id"],
            ["connector.id"],
            name="fk_data_source_connector_id_connector",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_data_source"),
        sa.UniqueConstraint(
            "connector_id", "external_id", name="uq_data_source_connector_external"
        ),
    )
    op.create_index("ix_data_source_connector_id", "data_source", ["connector_id"])

    op.create_table(
        "snapshot",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("data_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "status",
            snapshot_status,
            server_default="READY",
            nullable=False,
        ),
        sa.Column("record_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("schema_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "source_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["data_source_id"],
            ["data_source.id"],
            name="fk_snapshot_data_source_id_data_source",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_snapshot"),
    )
    op.create_index("ix_snapshot_data_source_id", "snapshot", ["data_source_id"])
    op.create_index(
        "ix_snapshot_source_captured", "snapshot", ["data_source_id", "captured_at"]
    )
    op.create_foreign_key(
        "fk_data_source_current_snapshot_id_snapshot",
        "data_source",
        "snapshot",
        ["current_snapshot_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "snapshot_record",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["snapshot.id"],
            name="fk_snapshot_record_snapshot_id_snapshot",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_snapshot_record"),
        sa.UniqueConstraint("snapshot_id", "row_index", name="uq_snapshot_record_row"),
    )
    op.create_index(
        "ix_snapshot_record_snapshot_id", "snapshot_record", ["snapshot_id"]
    )

    op.create_table(
        "data_source_permission",
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("data_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["department.id"],
            name="fk_data_source_permission_department_id_department",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["data_source_id"],
            ["data_source.id"],
            name="fk_data_source_permission_data_source_id_data_source",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by"],
            ["app_user.id"],
            name="fk_data_source_permission_granted_by_app_user",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "department_id", "data_source_id", name="pk_data_source_permission"
        ),
    )
    op.create_index(
        "ix_data_source_permission_data_source_id",
        "data_source_permission",
        ["data_source_id"],
    )

    op.create_table(
        "sync_job",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("data_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sync_status, server_default="RUNNING", nullable=False),
        sa.Column("trigger", sync_trigger, server_default="SCHEDULED", nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("record_count", sa.Integer(), nullable=True),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["data_source_id"],
            ["data_source.id"],
            name="fk_sync_job_data_source_id_data_source",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["app_user.id"],
            name="fk_sync_job_actor_user_id_app_user",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["snapshot.id"],
            name="fk_sync_job_snapshot_id_snapshot",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sync_job"),
    )
    op.create_index("ix_sync_job_data_source_id", "sync_job", ["data_source_id"])
    op.create_index(
        "ix_sync_job_source_started", "sync_job", ["data_source_id", "started_at"]
    )


def downgrade() -> None:
    op.drop_table("sync_job")
    op.drop_table("data_source_permission")
    op.drop_table("snapshot_record")
    op.drop_constraint(
        "fk_data_source_current_snapshot_id_snapshot", "data_source", type_="foreignkey"
    )
    op.drop_table("snapshot")
    op.drop_table("data_source")
    op.drop_table("connector_credential")
    op.drop_table("connector")

    postgresql.ENUM(name="snapshot_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="sync_trigger").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="sync_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="connector_type").drop(op.get_bind(), checkfirst=True)
