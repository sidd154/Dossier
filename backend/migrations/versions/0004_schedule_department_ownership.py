"""A mail schedule belongs to exactly one department.

Existing multi-department schedules are collapsed to their first department (by id).
Schedules that only had users are assigned the first user's department. Any schedule
that cannot be resolved is removed, because the new model requires an owner.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "mail_schedule",
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.execute(
        """
        UPDATE mail_schedule AS s
        SET department_id = picked.department_id
        FROM (
            SELECT schedule_id, MIN(department_id::text)::uuid AS department_id
            FROM mail_schedule_department
            GROUP BY schedule_id
        ) AS picked
        WHERE s.id = picked.schedule_id
        """
    )
    op.execute(
        """
        UPDATE mail_schedule AS s
        SET department_id = picked.department_id
        FROM (
            SELECT su.schedule_id, MIN(u.department_id::text)::uuid AS department_id
            FROM mail_schedule_user AS su
            JOIN app_user AS u ON u.id = su.user_id
            GROUP BY su.schedule_id
        ) AS picked
        WHERE s.id = picked.schedule_id AND s.department_id IS NULL
        """
    )
    op.execute("DELETE FROM mail_schedule WHERE department_id IS NULL")

    op.alter_column("mail_schedule", "department_id", nullable=False)
    op.create_foreign_key(
        "fk_mail_schedule_department_id_department",
        "mail_schedule",
        "department",
        ["department_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_mail_schedule_department_id", "mail_schedule", ["department_id"]
    )

    op.drop_table("mail_schedule_department")
    op.drop_table("mail_schedule_user")


def downgrade() -> None:
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

    op.execute(
        """
        INSERT INTO mail_schedule_department (schedule_id, department_id)
        SELECT id, department_id FROM mail_schedule
        """
    )

    op.drop_index("ix_mail_schedule_department_id", table_name="mail_schedule")
    op.drop_constraint(
        "fk_mail_schedule_department_id_department",
        "mail_schedule",
        type_="foreignkey",
    )
    op.drop_column("mail_schedule", "department_id")
