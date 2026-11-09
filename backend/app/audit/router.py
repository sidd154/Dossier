import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, require_admin
from app.api.schemas import Page
from app.audit.schemas import AuditLogRead
from app.audit.service import list_audit_logs

router = APIRouter(
    prefix="/audit-logs",
    tags=["admin:audit"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=Page[AuditLogRead])
async def list_audit_logs_endpoint(
    session: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    action: str | None = None,
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
) -> Page[AuditLogRead]:
    items, total = await list_audit_logs(
        session,
        actor_id=actor_id,
        entity_type=entity_type,
        action=action,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return Page[AuditLogRead](
        items=[AuditLogRead.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )
