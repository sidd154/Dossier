import uuid

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, require_admin
from app.api.schemas import Page
from app.data_sources.schemas import SyncJobRead
from app.data_sources.service import list_sync_jobs

router = APIRouter(
    prefix="/sync-jobs",
    tags=["admin:sync"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=Page[SyncJobRead])
async def list_sync_jobs_endpoint(
    session: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    data_source_id: uuid.UUID | None = None,
    status: str | None = None,
) -> Page[SyncJobRead]:
    items, total = await list_sync_jobs(
        session,
        data_source_id=data_source_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return Page[SyncJobRead](
        items=[SyncJobRead.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )
