"""Executing a department-owned mail schedule.

The permission boundary is applied before any data is read: only sources granted to
the schedule's department and selected on the schedule can enter the prompt. A
department with nothing permitted is skipped without generating or sending anything.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.exceptions import AppError, NotFoundError
from app.database.mixins import utcnow
from app.llm.factory import get_llm_provider
from app.mail.content import (
    build_context,
    build_messages,
    compose_body,
    generate_body,
    load_source_contexts,
    render_subject,
)
from app.mail.models import (
    MailDelivery,
    MailDeliveryStatus,
    MailExecution,
    MailExecutionStatus,
    MailSchedule,
)
from app.mail.preview_service import today_string
from app.mail.recipients import Recipient, resolve_recipients
from app.mail.sender import build_message, send_email
from app.mail.settings_service import build_smtp_config, get_mail_settings
from app.organisation.service import get_organisation
from app.permissions.context import resolve_allowed_source_ids


def _truncate(value: str, limit: int = 2000) -> str:
    return value[:limit]


def _add_delivery(
    session: AsyncSession,
    execution: MailExecution,
    recipient: Recipient,
    *,
    status: MailDeliveryStatus,
    error: str | None = None,
    subject: str | None = None,
    body: str | None = None,
    message_id: str | None = None,
) -> None:
    session.add(
        MailDelivery(
            execution_id=execution.id,
            recipient_user_id=recipient.user_id,
            email=recipient.email,
            department_id=recipient.department_id,
            status=status,
            error=_truncate(error) if error else None,
            subject=subject,
            body=body,
            message_id=message_id,
            sent_at=utcnow() if status == MailDeliveryStatus.SENT else None,
        )
    )
    if status == MailDeliveryStatus.SENT:
        execution.sent_count += 1
    elif status == MailDeliveryStatus.FAILED:
        execution.failed_count += 1
    else:
        execution.skipped_count += 1


async def _fail_execution(
    session: AsyncSession,
    execution: MailExecution,
    schedule: MailSchedule,
    message: str,
) -> MailExecution:
    execution.status = MailExecutionStatus.FAILED
    execution.error = _truncate(message)
    execution.finished_at = utcnow()
    schedule.last_run_at = execution.finished_at
    await session.commit()
    return execution


async def _finish(
    session: AsyncSession,
    execution: MailExecution,
    schedule: MailSchedule,
    *,
    error: str | None = None,
) -> MailExecution:
    if (
        execution.recipient_count
        and execution.failed_count == 0
        and execution.sent_count == 0
    ):
        execution.status = MailExecutionStatus.SKIPPED
    elif execution.failed_count and execution.sent_count:
        execution.status = MailExecutionStatus.PARTIAL
    elif execution.failed_count and not execution.sent_count:
        execution.status = MailExecutionStatus.FAILED
    elif execution.sent_count:
        execution.status = MailExecutionStatus.SUCCEEDED
    else:
        execution.status = MailExecutionStatus.SKIPPED

    if error is not None:
        execution.error = _truncate(error)
    execution.finished_at = utcnow()
    schedule.last_run_at = execution.finished_at
    await session.commit()
    return execution


async def _load_schedule(session: AsyncSession, schedule_id: uuid.UUID) -> MailSchedule:
    result = await session.execute(
        select(MailSchedule)
        .options(
            selectinload(MailSchedule.template),
            selectinload(MailSchedule.department),
            selectinload(MailSchedule.sources),
        )
        .where(MailSchedule.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()
    if schedule is None:
        raise NotFoundError("Mail schedule not found")
    return schedule


async def execute_execution(
    session: AsyncSession, execution_id: uuid.UUID
) -> MailExecution:
    execution = await session.get(MailExecution, execution_id)
    if execution is None:
        raise NotFoundError("Mail execution not found")
    if execution.status != MailExecutionStatus.RUNNING:
        return execution

    schedule = await _load_schedule(session, execution.schedule_id)
    settings = get_settings()

    organisation = await get_organisation(session)
    smtp_row = await get_mail_settings(session)
    if smtp_row is None:
        return await _fail_execution(
            session, execution, schedule, "SMTP settings are not configured"
        )

    try:
        config = build_smtp_config(smtp_row)
    except AppError as exc:
        return await _fail_execution(session, execution, schedule, exc.detail)

    recipients = await resolve_recipients(session, schedule)
    execution.recipient_count = len(recipients)
    if not recipients:
        return await _finish(
            session,
            execution,
            schedule,
            error="This department has no active members",
        )

    allowed = await resolve_allowed_source_ids(session, schedule.department_id)
    permitted = [
        source
        for source in schedule.sources
        if source.id in allowed and source.is_active
    ]
    if not permitted:
        for recipient in recipients:
            _add_delivery(
                session,
                execution,
                recipient,
                status=MailDeliveryStatus.SKIPPED,
                error="No permitted sources for this department",
            )
        await session.commit()
        return await _finish(session, execution, schedule)

    contexts = await load_source_contexts(
        session, sources=permitted, row_limit=schedule.row_limit
    )
    if not contexts:
        for recipient in recipients:
            _add_delivery(
                session,
                execution,
                recipient,
                status=MailDeliveryStatus.FAILED,
                error="The permitted sources have no snapshot yet",
            )
        await session.commit()
        return await _finish(session, execution, schedule)

    today = today_string(organisation.timezone)
    context = build_context(
        organisation=organisation,
        department_name=schedule.department.name,
        contexts=contexts,
        today=today,
        max_chars=settings.mail_max_prompt_chars,
    )
    messages = build_messages(
        template=schedule.template,
        organisation=organisation,
        department_name=schedule.department.name,
        context=context,
        today=today,
    )

    try:
        generated = await generate_body(
            provider=get_llm_provider(), messages=messages
        )
    except Exception as exc:
        for recipient in recipients:
            _add_delivery(
                session,
                execution,
                recipient,
                status=MailDeliveryStatus.FAILED,
                error=f"Generation failed: {type(exc).__name__}: {exc}",
            )
        await session.commit()
        return await _finish(session, execution, schedule)

    signature = smtp_row.from_name or organisation.name
    for recipient in recipients:
        subject = render_subject(
            subject_template=schedule.template.subject_template,
            organisation=organisation,
            department_name=recipient.department_name,
            recipient_name=recipient.full_name,
            recipient_email=recipient.email,
            today=today,
        )
        body = compose_body(
            recipient_name=recipient.full_name,
            generated=generated,
            signature=signature,
        )
        message = build_message(
            config, to_email=recipient.email, subject=subject, body=body
        )
        try:
            message_id = await send_email(
                config, message, retries=settings.mail_send_retries
            )
            _add_delivery(
                session,
                execution,
                recipient,
                status=MailDeliveryStatus.SENT,
                subject=subject,
                body=body,
                message_id=message_id,
            )
        except Exception as exc:
            _add_delivery(
                session,
                execution,
                recipient,
                status=MailDeliveryStatus.FAILED,
                error=f"{type(exc).__name__}: {exc}",
                subject=subject,
                body=body,
            )
    await session.commit()
    return await _finish(session, execution, schedule)
