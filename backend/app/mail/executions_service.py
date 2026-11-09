"""Execution queries and manual runs."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database.mixins import utcnow
from app.departments.models import Department
from app.mail.models import (
    MailDelivery,
    MailExecution,
    MailExecutionStatus,
    MailSchedule,
    MailTrigger,
)


async def create_manual_execution(
    session: AsyncSession, *, schedule_id: uuid.UUID
) -> MailExecution:
    schedule = await session.get(MailSchedule, schedule_id)
    if schedule is None:
        raise NotFoundError("Mail schedule not found")

    execution = MailExecution(
        schedule_id=schedule.id,
        trigger=MailTrigger.MANUAL,
        scheduled_for=utcnow(),
        status=MailExecutionStatus.RUNNING,
    )
    session.add(execution)
    await session.commit()
    return execution


async def list_executions(
    session: AsyncSession,
    *,
    schedule_id: uuid.UUID | None,
    department_id: uuid.UUID | None,
    status: str | None,
    page: int,
    page_size: int,
) -> tuple[list[tuple[MailExecution, str, str]], int]:
    conditions = []
    if schedule_id is not None:
        conditions.append(MailExecution.schedule_id == schedule_id)
    if department_id is not None:
        conditions.append(MailSchedule.department_id == department_id)
    if status:
        conditions.append(MailExecution.status == status)

    count_stmt = select(func.count()).select_from(MailExecution).join(
        MailSchedule, MailSchedule.id == MailExecution.schedule_id
    )
    list_stmt = (
        select(MailExecution, MailSchedule.name, Department.name)
        .join(MailSchedule, MailSchedule.id == MailExecution.schedule_id)
        .join(Department, Department.id == MailSchedule.department_id)
    )
    if conditions:
        count_stmt = count_stmt.where(*conditions)
        list_stmt = list_stmt.where(*conditions)

    total = await session.scalar(count_stmt) or 0
    rows = (
        await session.execute(
            list_stmt.order_by(MailExecution.started_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return [(row[0], row[1], row[2]) for row in rows], total


async def get_execution_detail(
    session: AsyncSession, execution_id: uuid.UUID
) -> tuple[MailExecution, str, str, list[MailDelivery]]:
    row = (
        await session.execute(
            select(MailExecution, MailSchedule.name, Department.name)
            .join(MailSchedule, MailSchedule.id == MailExecution.schedule_id)
            .join(Department, Department.id == MailSchedule.department_id)
            .where(MailExecution.id == execution_id)
        )
    ).one_or_none()
    if row is None:
        raise NotFoundError("Mail execution not found")

    deliveries = (
        await session.execute(
            select(MailDelivery)
            .where(MailDelivery.execution_id == execution_id)
            .order_by(MailDelivery.email.asc())
        )
    ).scalars().all()
    return row[0], row[1], row[2], list(deliveries)
