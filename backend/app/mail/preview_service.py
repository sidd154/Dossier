"""Template preview and test delivery.

Preview uses the same permission intersection as a real send, so what an admin sees is
what a recipient in that department would receive.
"""

import uuid
from datetime import UTC, datetime, tzinfo
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit
from app.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.data_sources.models import DataSource
from app.departments.models import Department
from app.llm.factory import get_llm_provider
from app.mail.content import (
    build_context,
    build_messages,
    compose_body,
    generate_body,
    load_source_contexts,
    render_subject,
)
from app.mail.models import MailTemplate
from app.mail.schemas import MailPreviewResponse
from app.mail.sender import build_message, send_email
from app.mail.settings_service import build_smtp_config, get_mail_settings
from app.organisation.models import Organisation
from app.organisation.service import get_organisation
from app.permissions.context import resolve_allowed_source_ids


def today_string(timezone: str) -> str:
    tz: tzinfo
    try:
        tz = ZoneInfo(timezone)
    except (KeyError, ValueError):
        tz = UTC
    return datetime.now(tz).strftime("%A, %d %B %Y")


async def _resolve_preview_sources(
    session: AsyncSession,
    *,
    department_id: uuid.UUID,
    source_ids: list[uuid.UUID],
) -> tuple[Department, list[DataSource], list[str]]:
    department = await session.get(Department, department_id)
    if department is None:
        raise NotFoundError("Department not found")

    unique_ids = list(dict.fromkeys(source_ids))
    rows = (
        await session.execute(select(DataSource).where(DataSource.id.in_(unique_ids)))
    ).scalars().all()
    if len(rows) != len(unique_ids):
        raise NotFoundError("One or more data sources do not exist")

    allowed = await resolve_allowed_source_ids(session, department_id)
    used = [source for source in rows if source.id in allowed and source.is_active]
    excluded = [source.name for source in rows if source.id not in allowed]
    return department, used, excluded


def _signature(organisation: Organisation, from_name: str | None) -> str:
    return from_name or organisation.name


async def generate_preview(
    session: AsyncSession,
    *,
    template: MailTemplate,
    department_id: uuid.UUID,
    source_ids: list[uuid.UUID],
    recipient_name: str = "Sample Recipient",
    recipient_email: str = "sample@example.com",
) -> MailPreviewResponse:
    settings = get_settings()
    department, used, excluded = await _resolve_preview_sources(
        session, department_id=department_id, source_ids=source_ids
    )
    if not used:
        raise ConflictError(
            "This department cannot access any of the selected sources",
            code="no_permitted_sources",
        )

    organisation = await get_organisation(session)
    contexts = await load_source_contexts(
        session, sources=used, row_limit=settings.mail_max_rows_per_source
    )
    if not contexts:
        raise ConflictError(
            "The selected sources have no snapshot yet", code="no_snapshot"
        )

    today = today_string(organisation.timezone)
    context = build_context(
        organisation=organisation,
        department_name=department.name,
        contexts=contexts,
        today=today,
        max_chars=settings.mail_max_prompt_chars,
    )
    messages = build_messages(
        template=template,
        organisation=organisation,
        department_name=department.name,
        context=context,
        today=today,
    )
    generated = await generate_body(provider=get_llm_provider(), messages=messages)

    smtp = await get_mail_settings(session)
    signature = _signature(organisation, smtp.from_name if smtp else None)
    subject = render_subject(
        subject_template=template.subject_template,
        organisation=organisation,
        department_name=department.name,
        recipient_name=recipient_name,
        recipient_email=recipient_email,
        today=today,
    )

    return MailPreviewResponse(
        subject=subject,
        body=compose_body(
            recipient_name=recipient_name, generated=generated, signature=signature
        ),
        sources_used=[source.name for source in used],
        sources_excluded=excluded,
    )


async def test_send(
    session: AsyncSession,
    *,
    template: MailTemplate,
    to_email: str,
    department_id: uuid.UUID,
    source_ids: list[uuid.UUID],
    actor_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> MailPreviewResponse:
    preview = await generate_preview(
        session,
        template=template,
        department_id=department_id,
        source_ids=source_ids,
        recipient_name="Test Recipient",
        recipient_email=to_email,
    )

    row = await get_mail_settings(session)
    if row is None:
        raise ConflictError("Configure SMTP settings first", code="smtp_missing")

    try:
        config = build_smtp_config(row)
        message = build_message(
            config, to_email=to_email, subject=preview.subject, body=preview.body
        )
        await send_email(config, message, retries=1)
    except Exception as exc:
        return MailPreviewResponse(
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
            subject=preview.subject,
            body=preview.body,
            sources_used=preview.sources_used,
            sources_excluded=preview.sources_excluded,
        )

    await record_audit(
        session,
        actor_id=actor_id,
        action="mail_template.test_sent",
        entity_type="mail_template",
        entity_id=str(template.id),
        after={"to": to_email, "department_id": str(department_id)},
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    return preview
