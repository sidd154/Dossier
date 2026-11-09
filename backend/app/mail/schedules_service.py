"""Mail schedule CRUD. A schedule belongs to exactly one department."""

import uuid
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit.service import record_audit
from app.core.exceptions import ConflictError, NotFoundError
from app.data_sources.models import DataSource
from app.departments.models import Department
from app.mail.models import MailFrequency, MailSchedule
from app.mail.schedule_time import next_run_for_schedule
from app.mail.schemas import MailScheduleCreate, MailScheduleRead, MailScheduleUpdate
from app.mail.templates_service import get_template


def _options() -> tuple[Any, ...]:
    return (
        selectinload(MailSchedule.template),
        selectinload(MailSchedule.department),
        selectinload(MailSchedule.sources),
    )


def to_read(schedule: MailSchedule) -> MailScheduleRead:
    return MailScheduleRead(
        id=schedule.id,
        name=schedule.name,
        template_id=schedule.template_id,
        template_name=schedule.template.name,
        department_id=schedule.department_id,
        department_name=schedule.department.name,
        enabled=schedule.enabled,
        frequency=schedule.frequency,
        time_of_day=schedule.time_of_day,
        weekday=schedule.weekday,
        day_of_month=schedule.day_of_month,
        timezone=schedule.timezone,
        row_limit=schedule.row_limit,
        next_run_at=schedule.next_run_at,
        last_run_at=schedule.last_run_at,
        source_ids=[source.id for source in schedule.sources],
        source_names=[source.name for source in schedule.sources],
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
    )


def _snapshot(schedule: MailSchedule) -> dict[str, object]:
    return {
        "name": schedule.name,
        "template_id": str(schedule.template_id),
        "department_id": str(schedule.department_id),
        "enabled": schedule.enabled,
        "frequency": schedule.frequency.value,
        "time_of_day": schedule.time_of_day.isoformat(),
        "weekday": schedule.weekday,
        "day_of_month": schedule.day_of_month,
        "timezone": schedule.timezone,
        "row_limit": schedule.row_limit,
        "source_ids": sorted(str(source.id) for source in schedule.sources),
        "next_run_at": schedule.next_run_at.isoformat()
        if schedule.next_run_at
        else None,
    }


def _validate_frequency(
    frequency: MailFrequency, weekday: int | None, day_of_month: int | None
) -> tuple[int | None, int | None]:
    if frequency == MailFrequency.DAILY:
        return None, None
    if frequency == MailFrequency.WEEKLY:
        if weekday is None:
            raise ConflictError(
                "Choose a weekday for a weekly schedule", code="invalid_schedule"
            )
        return weekday, None
    if day_of_month is None:
        raise ConflictError(
            "Choose a day of the month for a monthly schedule",
            code="invalid_schedule",
        )
    return None, day_of_month


def _validate_timezone(value: str) -> None:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ConflictError("Unknown timezone", code="invalid_timezone") from exc


async def _load_sources(
    session: AsyncSession, source_ids: list[uuid.UUID]
) -> list[DataSource]:
    unique_ids = list(dict.fromkeys(source_ids))
    rows = (
        await session.execute(
            select(DataSource).where(DataSource.id.in_(unique_ids))
        )
    ).scalars().all()
    if len(rows) != len(unique_ids):
        raise NotFoundError("One or more data sources do not exist")
    inactive = [source.name for source in rows if not source.is_active]
    if inactive:
        raise ConflictError(
            f"Inactive sources cannot be scheduled: {', '.join(inactive)}",
            code="source_inactive",
        )
    return list(rows)


async def _load_department(
    session: AsyncSession, department_id: uuid.UUID
) -> Department:
    department = await session.get(Department, department_id)
    if department is None:
        raise NotFoundError("Department not found")
    return department


async def load_schedule(session: AsyncSession, schedule_id: uuid.UUID) -> MailSchedule:
    result = await session.execute(
        select(MailSchedule).options(*_options()).where(MailSchedule.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()
    if schedule is None:
        raise NotFoundError("Mail schedule not found")
    return schedule


async def list_schedules(
    session: AsyncSession,
    *,
    department_id: uuid.UUID | None,
    q: str | None,
    enabled: bool | None,
    page: int,
    page_size: int,
) -> tuple[list[MailSchedule], int]:
    conditions = []
    if department_id is not None:
        conditions.append(MailSchedule.department_id == department_id)
    if q:
        conditions.append(MailSchedule.name.ilike(f"%{q.strip()}%"))
    if enabled is not None:
        conditions.append(MailSchedule.enabled.is_(enabled))

    count_stmt = select(func.count()).select_from(MailSchedule)
    list_stmt = select(MailSchedule).options(*_options())
    if conditions:
        count_stmt = count_stmt.where(*conditions)
        list_stmt = list_stmt.where(*conditions)

    total = await session.scalar(count_stmt) or 0
    items = (
        await session.execute(
            list_stmt.order_by(MailSchedule.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return list(items), total


async def create_schedule(
    session: AsyncSession,
    *,
    payload: MailScheduleCreate,
    actor_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> MailSchedule:
    name = payload.name.strip()
    if await session.scalar(select(MailSchedule.id).where(MailSchedule.name == name)):
        raise ConflictError(
            "A schedule with this name already exists", code="name_in_use"
        )

    template = await get_template(session, payload.template_id)
    if not template.is_active:
        raise ConflictError("This template is inactive", code="template_inactive")

    department = await _load_department(session, payload.department_id)
    sources = await _load_sources(session, payload.source_ids)

    _validate_timezone(payload.timezone)
    weekday, day_of_month = _validate_frequency(
        payload.frequency, payload.weekday, payload.day_of_month
    )

    schedule = MailSchedule(
        name=name,
        template_id=template.id,
        department_id=department.id,
        enabled=payload.enabled,
        frequency=payload.frequency,
        time_of_day=payload.time_of_day,
        weekday=weekday,
        day_of_month=day_of_month,
        timezone=payload.timezone,
        row_limit=payload.row_limit,
    )
    schedule.sources = sources
    schedule.next_run_at = (
        next_run_for_schedule(schedule) if payload.enabled else None
    )

    session.add(schedule)
    await session.flush()
    await record_audit(
        session,
        actor_id=actor_id,
        action="mail_schedule.created",
        entity_type="mail_schedule",
        entity_id=str(schedule.id),
        after=_snapshot(schedule),
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    return await load_schedule(session, schedule.id)


async def update_schedule(
    session: AsyncSession,
    *,
    schedule_id: uuid.UUID,
    payload: MailScheduleUpdate,
    actor_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> MailSchedule:
    schedule = await load_schedule(session, schedule_id)
    changes = payload.model_dump(exclude_unset=True)
    before = _snapshot(schedule)

    source_ids = changes.pop("source_ids", None)

    if "name" in changes and changes["name"] is not None:
        name = str(changes["name"]).strip()
        clash = await session.scalar(
            select(MailSchedule.id).where(
                MailSchedule.name == name, MailSchedule.id != schedule.id
            )
        )
        if clash is not None:
            raise ConflictError(
                "A schedule with this name already exists", code="name_in_use"
            )
        changes["name"] = name

    if "template_id" in changes and changes["template_id"] is not None:
        template = await get_template(session, changes["template_id"])
        if not template.is_active:
            raise ConflictError("This template is inactive", code="template_inactive")

    if "department_id" in changes and changes["department_id"] is not None:
        await _load_department(session, changes["department_id"])

    if "timezone" in changes and changes["timezone"] is not None:
        _validate_timezone(str(changes["timezone"]))

    for field, value in changes.items():
        setattr(schedule, field, value)

    if source_ids is not None:
        if not source_ids:
            raise ConflictError("Select at least one data source", code="no_sources")
        schedule.sources = await _load_sources(session, source_ids)

    schedule.weekday, schedule.day_of_month = _validate_frequency(
        schedule.frequency, schedule.weekday, schedule.day_of_month
    )
    schedule.next_run_at = (
        next_run_for_schedule(schedule) if schedule.enabled else None
    )

    await session.flush()
    await record_audit(
        session,
        actor_id=actor_id,
        action="mail_schedule.updated",
        entity_type="mail_schedule",
        entity_id=str(schedule.id),
        before=before,
        after=_snapshot(schedule),
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    return await load_schedule(session, schedule.id)


async def delete_schedule(
    session: AsyncSession,
    *,
    schedule_id: uuid.UUID,
    actor_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> None:
    schedule = await load_schedule(session, schedule_id)
    before = _snapshot(schedule)
    await session.delete(schedule)
    await record_audit(
        session,
        actor_id=actor_id,
        action="mail_schedule.deleted",
        entity_type="mail_schedule",
        entity_id=str(schedule_id),
        before=before,
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
