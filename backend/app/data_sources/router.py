import uuid

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import AdminUser, DbSession, Meta, require_admin
from app.api.schemas import Page
from app.data_sources.schemas import (
    DataSourceCreate,
    DataSourceRead,
    DataSourceUpdate,
    SnapshotRead,
    SyncJobRead,
)
from app.data_sources.service import (
    create_data_source,
    delete_data_source,
    get_data_source,
    list_data_sources,
    list_snapshots,
    list_sync_jobs,
    to_read,
    update_data_source,
)
from app.sync.models import SyncTrigger
from app.sync.service import run_sync

router = APIRouter(
    prefix="/data-sources",
    tags=["admin:data-sources"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=Page[DataSourceRead])
async def list_data_sources_endpoint(
    session: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    connector_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    q: str | None = None,
) -> Page[DataSourceRead]:
    items, total = await list_data_sources(
        session,
        connector_id=connector_id,
        is_active=is_active,
        q=q,
        page=page,
        page_size=page_size,
    )
    return Page[DataSourceRead](
        items=[to_read(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=DataSourceRead, status_code=201)
async def create_data_source_endpoint(
    payload: DataSourceCreate,
    session: DbSession,
    admin: AdminUser,
    meta: Meta,
) -> DataSourceRead:
    source = await create_data_source(
        session,
        payload=payload,
        actor_id=admin.id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    return to_read(source)


@router.get("/{data_source_id}", response_model=DataSourceRead)
async def get_data_source_endpoint(
    data_source_id: uuid.UUID, session: DbSession
) -> DataSourceRead:
    return to_read(await get_data_source(session, data_source_id))


@router.patch("/{data_source_id}", response_model=DataSourceRead)
async def update_data_source_endpoint(
    data_source_id: uuid.UUID,
    payload: DataSourceUpdate,
    session: DbSession,
    admin: AdminUser,
    meta: Meta,
) -> DataSourceRead:
    source = await update_data_source(
        session,
        data_source_id=data_source_id,
        payload=payload,
        actor_id=admin.id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    return to_read(source)


@router.delete("/{data_source_id}", status_code=204)
async def delete_data_source_endpoint(
    data_source_id: uuid.UUID,
    session: DbSession,
    admin: AdminUser,
    meta: Meta,
) -> Response:
    await delete_data_source(
        session,
        data_source_id=data_source_id,
        actor_id=admin.id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    return Response(status_code=204)


@router.post("/{data_source_id}/sync", response_model=SyncJobRead)
async def trigger_sync_endpoint(
    data_source_id: uuid.UUID,
    session: DbSession,
    admin: AdminUser,
) -> SyncJobRead:
    # Run inline so the admin sees the outcome immediately. Scheduled runs use the
    # same service through Celery.
    job = await run_sync(
        session,
        data_source_id=data_source_id,
        trigger=SyncTrigger.MANUAL,
        actor_id=admin.id,
    )
    return SyncJobRead.model_validate(job)


@router.get("/{data_source_id}/snapshots", response_model=Page[SnapshotRead])
async def list_snapshots_endpoint(
    data_source_id: uuid.UUID,
    session: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> Page[SnapshotRead]:
    items, total = await list_snapshots(
        session, data_source_id=data_source_id, page=page, page_size=page_size
    )
    return Page[SnapshotRead](
        items=[SnapshotRead.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{data_source_id}/sync-jobs", response_model=Page[SyncJobRead])
async def list_source_sync_jobs_endpoint(
    data_source_id: uuid.UUID,
    session: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> Page[SyncJobRead]:
    items, total = await list_sync_jobs(
        session,
        data_source_id=data_source_id,
        status=None,
        page=page,
        page_size=page_size,
    )
    return Page[SyncJobRead](
        items=[SyncJobRead.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )

