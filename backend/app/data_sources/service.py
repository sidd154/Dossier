"""Data source registration and department grants."""

import uuid
from typing import Any

from sqlalchemy import delete, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit.service import record_audit
from app.connectors.base import ConnectorError
from app.connectors.service import build_adapter, get_connector_model
from app.core.exceptions import ConflictError, NotFoundError, UpstreamError
from app.data_sources.models import DataSource, DataSourcePermission
from app.data_sources.schemas import (
    DataSourceCreate,
    DataSourceRead,
    DataSourceUpdate,
    DepartmentSourceEntry,
    DepartmentSourcesRead,
    SnapshotSummary,
)
from app.database.mixins import utcnow
from app.departments.models import Department
from app.snapshots.models import Snapshot
from app.sync.models import SyncJob


def _summary(snapshot: Snapshot) -> SnapshotSummary:
    return SnapshotSummary(
        id=snapshot.id,
        captured_at=snapshot.captured_at,
        status=snapshot.status,
        record_count=snapshot.record_count,
    )


def to_read(source: DataSource) -> DataSourceRead:
    current = source.current_snapshot
    return DataSourceRead(
        id=source.id,
        connector_id=source.connector_id,
        connector_name=source.connector.name,
        connector_type=source.connector.type.value,
        external_id=source.external_id,
        name=source.name,
        kind=source.kind,
        config=dict(source.config),
        is_active=source.is_active,
        schema_hash=source.schema_hash,
        current_snapshot=_summary(current) if current is not None else None,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def _audit_snapshot(source: DataSource) -> dict[str, object]:
    return {
        "name": source.name,
        "external_id": source.external_id,
        "kind": source.kind,
        "is_active": source.is_active,
        "connector_id": str(source.connector_id),
    }


async def list_data_sources(
    session: AsyncSession,
    *,
    connector_id: uuid.UUID | None,
    is_active: bool | None,
    q: str | None,
    page: int,
    page_size: int,
) -> tuple[list[DataSource], int]:
    conditions: list[Any] = []
    if connector_id is not None:
        conditions.append(DataSource.connector_id == connector_id)
    if is_active is not None:
        conditions.append(DataSource.is_active.is_(is_active))
    if q:
        like = f"%{q.strip()}%"
        conditions.append(or_(DataSource.name.ilike(like), DataSource.external_id.ilike(like)))

    count_stmt = select(func.count()).select_from(DataSource)
    list_stmt = select(DataSource).options(
        selectinload(DataSource.connector),
        selectinload(DataSource.current_snapshot),
    )
    if conditions:
        count_stmt = count_stmt.where(*conditions)
        list_stmt = list_stmt.where(*conditions)

    total = await session.scalar(count_stmt) or 0
    items = (
        await session.execute(
            list_stmt.order_by(DataSource.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return list(items), total


async def get_data_source(session: AsyncSession, data_source_id: uuid.UUID) -> DataSource:
    result = await session.execute(
        select(DataSource)
        .options(
            selectinload(DataSource.connector),
            selectinload(DataSource.current_snapshot),
        )
        .where(DataSource.id == data_source_id)
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise NotFoundError("Data source not found")
    return source


async def create_data_source(
    session: AsyncSession,
    *,
    payload: DataSourceCreate,
    actor_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> DataSource:
    connector = await get_connector_model(session, payload.connector_id)
    if not connector.is_active:
        raise ConflictError("The connector is inactive", code="connector_inactive")

    try:
        assets = await build_adapter(connector).list_assets()
    except ConnectorError as exc:
        raise UpstreamError(str(exc)) from exc

    asset = next(
        (item for item in assets if item.external_id == payload.external_id), None
    )
    if asset is None:
        raise NotFoundError("That asset was not found on the connector")

    existing = await session.scalar(
        select(DataSource.id).where(
            DataSource.connector_id == connector.id,
            DataSource.external_id == asset.external_id,
        )
    )
    if existing is not None:
        raise ConflictError("This source is already registered", code="source_exists")

    source = DataSource(
        connector_id=connector.id,
        external_id=asset.external_id,
        name=(payload.name or asset.name).strip(),
        kind=asset.kind,
        config=dict(asset.config),
        is_active=payload.is_active,
    )
    session.add(source)
    await session.flush()

    await record_audit(
        session,
        actor_id=actor_id,
        action="data_source.created",
        entity_type="data_source",
        entity_id=str(source.id),
        after=_audit_snapshot(source),
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    return await get_data_source(session, source.id)


async def update_data_source(
    session: AsyncSession,
    *,
    data_source_id: uuid.UUID,
    payload: DataSourceUpdate,
    actor_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> DataSource:
    source = await get_data_source(session, data_source_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return source

    before = _audit_snapshot(source)
    for field, value in changes.items():
        if field == "name" and value is not None:
            value = str(value).strip()
        setattr(source, field, value)

    await session.flush()
    await record_audit(
        session,
        actor_id=actor_id,
        action="data_source.updated",
        entity_type="data_source",
        entity_id=str(source.id),
        before=before,
        after=_audit_snapshot(source),
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    return await get_data_source(session, source.id)


async def delete_data_source(
    session: AsyncSession,
    *,
    data_source_id: uuid.UUID,
    actor_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> None:
    source = await get_data_source(session, data_source_id)
    before = _audit_snapshot(source)
    await session.delete(source)
    await record_audit(
        session,
        actor_id=actor_id,
        action="data_source.deleted",
        entity_type="data_source",
        entity_id=str(data_source_id),
        before=before,
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()


async def list_sync_jobs(
    session: AsyncSession,
    *,
    data_source_id: uuid.UUID | None,
    status: str | None,
    page: int,
    page_size: int,
) -> tuple[list[SyncJob], int]:
    conditions: list[Any] = []
    if data_source_id is not None:
        conditions.append(SyncJob.data_source_id == data_source_id)
    if status:
        conditions.append(SyncJob.status == status)

    count_stmt = select(func.count()).select_from(SyncJob)
    list_stmt = select(SyncJob)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
        list_stmt = list_stmt.where(*conditions)

    total = await session.scalar(count_stmt) or 0
    items = (
        await session.execute(
            list_stmt.order_by(SyncJob.started_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return list(items), total


async def list_snapshots(
    session: AsyncSession,
    *,
    data_source_id: uuid.UUID,
    page: int,
    page_size: int,
) -> tuple[list[Snapshot], int]:
    await get_data_source(session, data_source_id)
    total = await session.scalar(
        select(func.count())
        .select_from(Snapshot)
        .where(Snapshot.data_source_id == data_source_id)
    ) or 0
    items = (
        await session.execute(
            select(Snapshot)
            .where(Snapshot.data_source_id == data_source_id)
            .order_by(Snapshot.captured_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return list(items), total


async def get_department_sources(
    session: AsyncSession, department_id: uuid.UUID
) -> DepartmentSourcesRead:
    department = await session.get(Department, department_id)
    if department is None:
        raise NotFoundError("Department not found")

    granted = set(
        (
            await session.execute(
                select(DataSourcePermission.data_source_id).where(
                    DataSourcePermission.department_id == department_id
                )
            )
        ).scalars()
    )
    rows = (
        await session.execute(
            select(DataSource)
            .options(
                selectinload(DataSource.connector),
                selectinload(DataSource.current_snapshot),
            )
            .order_by(DataSource.name.asc())
        )
    ).scalars().all()

    return DepartmentSourcesRead(
        department_id=department.id,
        department_name=department.name,
        entries=[
            DepartmentSourceEntry(
                data_source_id=source.id,
                name=source.name,
                kind=source.kind,
                connector_name=source.connector.name,
                granted=source.id in granted,
                is_active=source.is_active,
                last_sync_at=(
                    source.current_snapshot.captured_at
                    if source.current_snapshot is not None
                    else None
                ),
                snapshot_status=(
                    source.current_snapshot.status.value
                    if source.current_snapshot is not None
                    else None
                ),
            )
            for source in rows
        ],
    )


async def set_department_sources(
    session: AsyncSession,
    *,
    department_id: uuid.UUID,
    data_source_ids: list[uuid.UUID],
    actor_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> DepartmentSourcesRead:
    department = await session.get(Department, department_id)
    if department is None:
        raise NotFoundError("Department not found")

    requested = set(data_source_ids)
    if requested:
        known = set(
            (
                await session.execute(
                    select(DataSource.id).where(DataSource.id.in_(requested))
                )
            ).scalars()
        )
        missing = requested - known
        if missing:
            raise NotFoundError("One or more data sources do not exist")

    current = set(
        (
            await session.execute(
                select(DataSourcePermission.data_source_id).where(
                    DataSourcePermission.department_id == department_id
                )
            )
        ).scalars()
    )
    to_add = requested - current
    to_remove = current - requested

    if to_remove:
        await session.execute(
            delete(DataSourcePermission).where(
                DataSourcePermission.department_id == department_id,
                DataSourcePermission.data_source_id.in_(to_remove),
            )
        )
    if to_add:
        await session.execute(
            insert(DataSourcePermission),
            [
                {
                    "department_id": department_id,
                    "data_source_id": source_id,
                    "granted_by": actor_id,
                    "granted_at": utcnow(),
                }
                for source_id in to_add
            ],
        )

    await record_audit(
        session,
        actor_id=actor_id,
        action="department.permissions_updated",
        entity_type="department",
        entity_id=str(department_id),
        before={"granted": sorted(str(item) for item in current)},
        after={"granted": sorted(str(item) for item in requested)},
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    return await get_department_sources(session, department_id)
