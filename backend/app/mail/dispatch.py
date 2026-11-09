"""Find due schedules and create their executions.

Running every minute is cheap: the query is indexed on ``next_run_at`` and the unique
execution slot makes a repeated tick harmless.
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mixins import utcnow
from app.mail.models import (
    MailExecution,
    MailExecutionStatus,
    MailSchedule,
    MailTrigger,
)
from app.mail.schedule_time import next_run_for_schedule


async def dispatch_due_schedules(
    session: AsyncSession, *, now: datetime | None = None
) -> list[uuid.UUID]:
    current = now or utcnow()
    schedules = (
        await session.execute(
            select(MailSchedule)
            .where(
                MailSchedule.enabled.is_(True),
                MailSchedule.next_run_at.is_not(None),
                MailSchedule.next_run_at <= current,
            )
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()

    execution_ids: list[uuid.UUID] = []
    for schedule in schedules:
        scheduled_for = schedule.next_run_at
        # Advance from now, not from the missed slot: a digest should not send a
        # backlog of one email per missed day.
        schedule.next_run_at = next_run_for_schedule(schedule, after=current)

        statement = (
            pg_insert(MailExecution)
            .values(
                schedule_id=schedule.id,
                trigger=MailTrigger.SCHEDULED,
                scheduled_for=scheduled_for,
                status=MailExecutionStatus.RUNNING,
            )
            .on_conflict_do_nothing(constraint="uq_mail_execution_slot")
            .returning(MailExecution.id)
        )
        execution_id = (await session.execute(statement)).scalar_one_or_none()
        if execution_id is not None:
            execution_ids.append(execution_id)

    await session.commit()
    return execution_ids
