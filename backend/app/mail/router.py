import uuid

from fastapi import APIRouter, Depends, Query, Response, status as http_status

from app.api.deps import AdminUser, DbSession, Meta, require_admin
from app.api.schemas import Page
from app.core.exceptions import NotFoundError, UpstreamError
from app.database.mixins import utcnow
from app.mail.executions_service import (
    create_manual_execution,
    get_execution_detail,
    list_executions,
)
from app.mail.models import MailExecutionStatus
from app.mail.preview_service import generate_preview, test_send
from app.mail.schedules_service import (
    create_schedule,
    delete_schedule,
    list_schedules,
    load_schedule,
    to_read as schedule_to_read,
    update_schedule,
)
from app.mail.schemas import (
    MailDeliveryRead,
    MailExecutionDetail,
    MailExecutionRead,
    MailExecutionSummary,
    MailPreviewRequest,
    MailPreviewResponse,
    MailRunResponse,
    MailScheduleCreate,
    MailScheduleRead,
    MailScheduleUpdate,
    MailSettingsRead,
    MailSettingsUpdate,
    MailTemplateCreate,
    MailTemplateRead,
    MailTemplateTestRequest,
    MailTemplateUpdate,
    MailTestResult,
    MailTestSendRequest,
)
from app.mail.settings_service import (
    get_mail_settings,
    test_mail_settings,
    to_read as settings_to_read,
    update_mail_settings,
)
from app.mail.templates_service import (
    create_template,
    delete_template,
    get_template,
    list_templates,
    update_template,
)

router = APIRouter(
    prefix="/mail",
    tags=["admin:mail"],
    dependencies=[Depends(require_admin)],
)


# ------------------------------------------------------------------ settings


@router.get("/settings", response_model=MailSettingsRead)
async def get_mail_settings_endpoint(session: DbSession) -> MailSettingsRead:
    row = await get_mail_settings(session)
    if row is None:
        raise NotFoundError("SMTP settings are not configured")
    return settings_to_read(row)


@router.patch("/settings", response_model=MailSettingsRead)
async def update_mail_settings_endpoint(
    payload: MailSettingsUpdate,
    session: DbSession,
    admin: AdminUser,
    meta: Meta,
) -> MailSettingsRead:
    row = await update_mail_settings(
        session,
        payload=payload,
        actor_id=admin.id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    return settings_to_read(row)


@router.post("/settings/test", response_model=MailTestResult)
async def test_mail_settings_endpoint(
    payload: MailTestSendRequest, session: DbSession
) -> MailTestResult:
    return await test_mail_settings(session, to_email=str(payload.to))


# ------------------------------------------------------------------ templates


@router.get("/templates", response_model=Page[MailTemplateRead])
async def list_templates_endpoint(
    session: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    is_active: bool | None = None,
) -> Page[MailTemplateRead]:
    items, total = await list_templates(
        session, q=q, is_active=is_active, page=page, page_size=page_size
    )
    return Page[MailTemplateRead](
        items=[MailTemplateRead.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/templates", response_model=MailTemplateRead, status_code=201)
async def create_template_endpoint(
    payload: MailTemplateCreate,
    session: DbSession,
    admin: AdminUser,
    meta: Meta,
) -> MailTemplateRead:
    template = await create_template(
        session,
        payload=payload,
        actor_id=admin.id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    return MailTemplateRead.model_validate(template)


@router.get("/templates/{template_id}", response_model=MailTemplateRead)
async def get_template_endpoint(
    template_id: uuid.UUID, session: DbSession
) -> MailTemplateRead:
    return MailTemplateRead.model_validate(await get_template(session, template_id))


@router.patch("/templates/{template_id}", response_model=MailTemplateRead)
async def update_template_endpoint(
    template_id: uuid.UUID,
    payload: MailTemplateUpdate,
    session: DbSession,
    admin: AdminUser,
    meta: Meta,
) -> MailTemplateRead:
    template = await update_template(
        session,
        template_id=template_id,
        payload=payload,
        actor_id=admin.id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    return MailTemplateRead.model_validate(template)


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template_endpoint(
    template_id: uuid.UUID,
    session: DbSession,
    admin: AdminUser,
    meta: Meta,
) -> Response:
    await delete_template(
        session,
        template_id=template_id,
        actor_id=admin.id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    return Response(status_code=204)


@router.post("/templates/{template_id}/preview", response_model=MailPreviewResponse)
async def preview_template_endpoint(
    template_id: uuid.UUID,
    payload: MailPreviewRequest,
    session: DbSession,
) -> MailPreviewResponse:
    template = await get_template(session, template_id)
    return await generate_preview(
        session,
        template=template,
        department_id=payload.department_id,
        source_ids=payload.source_ids,
    )


@router.post("/templates/{template_id}/test-send", response_model=MailPreviewResponse)
async def test_send_template_endpoint(
    template_id: uuid.UUID,
    payload: MailTemplateTestRequest,
    session: DbSession,
    admin: AdminUser,
    meta: Meta,
) -> MailPreviewResponse:
    template = await get_template(session, template_id)
    return await test_send(
        session,
        template=template,
        to_email=str(payload.to),
        department_id=payload.department_id,
        source_ids=payload.source_ids,
        actor_id=admin.id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )


# ------------------------------------------------------------------ schedules


@router.get("/schedules", response_model=Page[MailScheduleRead])
async def list_schedules_endpoint(
    session: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    enabled: bool | None = None,
    department_id: uuid.UUID | None = None,
) -> Page[MailScheduleRead]:
    items, total = await list_schedules(
        session,
        department_id=department_id,
        q=q,
        enabled=enabled,
        page=page,
        page_size=page_size,
    )
    return Page[MailScheduleRead](
        items=[schedule_to_read(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/schedules", response_model=MailScheduleRead, status_code=201)
async def create_schedule_endpoint(
    payload: MailScheduleCreate,
    session: DbSession,
    admin: AdminUser,
    meta: Meta,
) -> MailScheduleRead:
    schedule = await create_schedule(
        session,
        payload=payload,
        actor_id=admin.id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    return schedule_to_read(schedule)


@router.get("/schedules/{schedule_id}", response_model=MailScheduleRead)
async def get_schedule_endpoint(
    schedule_id: uuid.UUID, session: DbSession
) -> MailScheduleRead:
    return schedule_to_read(await load_schedule(session, schedule_id))


@router.patch("/schedules/{schedule_id}", response_model=MailScheduleRead)
async def update_schedule_endpoint(
    schedule_id: uuid.UUID,
    payload: MailScheduleUpdate,
    session: DbSession,
    admin: AdminUser,
    meta: Meta,
) -> MailScheduleRead:
    schedule = await update_schedule(
        session,
        schedule_id=schedule_id,
        payload=payload,
        actor_id=admin.id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    return schedule_to_read(schedule)


@router.delete("/schedules/{schedule_id}", status_code=204)
async def delete_schedule_endpoint(
    schedule_id: uuid.UUID,
    session: DbSession,
    admin: AdminUser,
    meta: Meta,
) -> Response:
    await delete_schedule(
        session,
        schedule_id=schedule_id,
        actor_id=admin.id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    return Response(status_code=204)


@router.post(
    "/schedules/{schedule_id}/run",
    response_model=MailRunResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
async def run_schedule_endpoint(
    schedule_id: uuid.UUID, session: DbSession
) -> MailRunResponse:
    execution = await create_manual_execution(session, schedule_id=schedule_id)

    from app.workers.tasks import execute_mail_execution

    try:
        execute_mail_execution.delay(str(execution.id))
    except Exception as exc:
        execution.status = MailExecutionStatus.FAILED
        execution.error = "Could not enqueue the execution"
        execution.finished_at = utcnow()
        await session.commit()
        raise UpstreamError("The mail worker is unavailable") from exc

    return MailRunResponse(execution_id=execution.id, status=execution.status)


# ------------------------------------------------------------------ executions


@router.get("/executions", response_model=Page[MailExecutionSummary])
async def list_executions_endpoint(
    session: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    schedule_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    status: str | None = None,
) -> Page[MailExecutionSummary]:
    items, total = await list_executions(
        session,
        schedule_id=schedule_id,
        department_id=department_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    summaries = []
    for execution, schedule_name, department_name in items:
        base = MailExecutionRead.model_validate(execution)
        summaries.append(
            MailExecutionSummary(
                **base.model_dump(),
                schedule_name=schedule_name,
                department_name=department_name,
            )
        )
    return Page[MailExecutionSummary](
        items=summaries, total=total, page=page, page_size=page_size
    )


@router.get("/executions/{execution_id}", response_model=MailExecutionDetail)
async def get_execution_endpoint(
    execution_id: uuid.UUID, session: DbSession
) -> MailExecutionDetail:
    execution, schedule_name, department_name, deliveries = await get_execution_detail(
        session, execution_id
    )
    base = MailExecutionRead.model_validate(execution)
    return MailExecutionDetail(
        **base.model_dump(),
        schedule_name=schedule_name,
        department_name=department_name,
        deliveries=[MailDeliveryRead.model_validate(item) for item in deliveries],
    )

