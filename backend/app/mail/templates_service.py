"""Mail template CRUD. The template is the system prompt for generation."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit
from app.core.exceptions import ConflictError, NotFoundError
from app.mail.models import MailSchedule, MailTemplate
from app.mail.schemas import MailTemplateCreate, MailTemplateUpdate


def _snapshot(template: MailTemplate) -> dict[str, object]:
    # The prompt itself is not duplicated into the audit log; its length is enough
    # to see that it changed.
    return {
        "name": template.name,
        "subject_template": template.subject_template,
        "prompt_length": len(template.system_prompt),
        "is_active": template.is_active,
    }


async def list_templates(
    session: AsyncSession,
    *,
    q: str | None,
    is_active: bool | None,
    page: int,
    page_size: int,
) -> tuple[list[MailTemplate], int]:
    conditions = []
    if q:
        like = f"%{q.strip()}%"
        conditions.append(MailTemplate.name.ilike(like))
    if is_active is not None:
        conditions.append(MailTemplate.is_active.is_(is_active))

    count_stmt = select(func.count()).select_from(MailTemplate)
    list_stmt = select(MailTemplate)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
        list_stmt = list_stmt.where(*conditions)

    total = await session.scalar(count_stmt) or 0
    items = (
        await session.execute(
            list_stmt.order_by(MailTemplate.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return list(items), total


async def get_template(session: AsyncSession, template_id: uuid.UUID) -> MailTemplate:
    template = await session.get(MailTemplate, template_id)
    if template is None:
        raise NotFoundError("Mail template not found")
    return template


async def create_template(
    session: AsyncSession,
    *,
    payload: MailTemplateCreate,
    actor_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> MailTemplate:
    name = payload.name.strip()
    if await session.scalar(select(MailTemplate.id).where(MailTemplate.name == name)):
        raise ConflictError(
            "A template with this name already exists", code="name_in_use"
        )

    template = MailTemplate(
        name=name,
        description=payload.description,
        subject_template=payload.subject_template.strip(),
        system_prompt=payload.system_prompt.strip(),
        is_active=payload.is_active,
    )
    session.add(template)
    await session.flush()

    await record_audit(
        session,
        actor_id=actor_id,
        action="mail_template.created",
        entity_type="mail_template",
        entity_id=str(template.id),
        after=_snapshot(template),
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    return template


async def update_template(
    session: AsyncSession,
    *,
    template_id: uuid.UUID,
    payload: MailTemplateUpdate,
    actor_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> MailTemplate:
    template = await get_template(session, template_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return template

    if "name" in changes and changes["name"] is not None:
        name = str(changes["name"]).strip()
        clash = await session.scalar(
            select(MailTemplate.id).where(
                MailTemplate.name == name, MailTemplate.id != template.id
            )
        )
        if clash is not None:
            raise ConflictError(
                "A template with this name already exists", code="name_in_use"
            )
        changes["name"] = name

    before = _snapshot(template)
    for field, value in changes.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(template, field, value)
    await session.flush()

    await record_audit(
        session,
        actor_id=actor_id,
        action="mail_template.updated",
        entity_type="mail_template",
        entity_id=str(template.id),
        before=before,
        after=_snapshot(template),
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    return template


async def delete_template(
    session: AsyncSession,
    *,
    template_id: uuid.UUID,
    actor_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> None:
    template = await get_template(session, template_id)
    in_use = await session.scalar(
        select(func.count())
        .select_from(MailSchedule)
        .where(MailSchedule.template_id == template.id)
    )
    if in_use:
        raise ConflictError(
            "This template is used by a schedule; delete or reassign the schedule first.",
            code="template_in_use",
        )

    before = _snapshot(template)
    await session.delete(template)
    await record_audit(
        session,
        actor_id=actor_id,
        action="mail_template.deleted",
        entity_type="mail_template",
        entity_id=str(template_id),
        before=before,
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
