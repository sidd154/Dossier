"""Recipient resolution for a department-owned schedule."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.mail.models import MailSchedule
from app.users.models import AccountStatus, AppUser


@dataclass(frozen=True, slots=True)
class Recipient:
    user_id: uuid.UUID
    email: str
    full_name: str
    department_id: uuid.UUID
    department_name: str


async def resolve_recipients(
    session: AsyncSession, schedule: MailSchedule
) -> list[Recipient]:
    """Active members of the schedule's department, deduplicated by email."""
    rows = (
        await session.execute(
            select(AppUser)
            .options(selectinload(AppUser.department))
            .where(
                AppUser.department_id == schedule.department_id,
                AppUser.status == AccountStatus.ACTIVE,
            )
        )
    ).scalars().all()

    seen: set[str] = set()
    recipients: list[Recipient] = []
    for user in sorted(rows, key=lambda item: item.email.lower()):
        email = user.email.lower()
        if email in seen:
            continue
        seen.add(email)
        recipients.append(
            Recipient(
                user_id=user.id,
                email=email,
                full_name=user.full_name,
                department_id=user.department_id,
                department_name=user.department.name,
            )
        )
    return recipients
