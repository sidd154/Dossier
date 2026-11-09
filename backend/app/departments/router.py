import uuid

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import AdminUser, DbSession, Meta, require_admin
from app.api.schemas import Page
from app.data_sources.schemas import DepartmentSourcesRead, DepartmentSourcesUpdate
from app.data_sources.service import get_department_sources, set_department_sources
from app.departments.schemas import DepartmentCreate, DepartmentRead, DepartmentUpdate
from app.departments.service import (
    create_department,
    delete_department,
    get_department,
    list_departments,
    update_department,
)

router = APIRouter(
    prefix="/departments",
    tags=["admin:departments"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=Page[DepartmentRead])
async def list_departments_endpoint(
    session: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    is_active: bool | None = None,
) -> Page[DepartmentRead]:
    items, total = await list_departments(
        session, q=q, is_active=is_active, page=page, page_size=page_size
    )
    return Page[DepartmentRead](
        items=[DepartmentRead.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=DepartmentRead, status_code=201)
async def create_department_endpoint(
    payload: DepartmentCreate,
    session: DbSession,
    admin: AdminUser,
    meta: Meta,
) -> DepartmentRead:
    department = await create_department(
        session,
        payload=payload,
        actor_id=admin.id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    return DepartmentRead.model_validate(department)


@router.get("/{department_id}", response_model=DepartmentRead)
async def get_department_endpoint(
    department_id: uuid.UUID, session: DbSession
) -> DepartmentRead:
    return DepartmentRead.model_validate(await get_department(session, department_id))


@router.patch("/{department_id}", response_model=DepartmentRead)
async def update_department_endpoint(
    department_id: uuid.UUID,
    payload: DepartmentUpdate,
    session: DbSession,
    admin: AdminUser,
    meta: Meta,
) -> DepartmentRead:
    department = await update_department(
        session,
        department_id=department_id,
        payload=payload,
        actor_id=admin.id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    return DepartmentRead.model_validate(department)


@router.get("/{department_id}/sources", response_model=DepartmentSourcesRead)
async def get_department_sources_endpoint(
    department_id: uuid.UUID, session: DbSession
) -> DepartmentSourcesRead:
    return await get_department_sources(session, department_id)


@router.put("/{department_id}/sources", response_model=DepartmentSourcesRead)
async def set_department_sources_endpoint(
    department_id: uuid.UUID,
    payload: DepartmentSourcesUpdate,
    session: DbSession,
    admin: AdminUser,
    meta: Meta,
) -> DepartmentSourcesRead:
    return await set_department_sources(
        session,
        department_id=department_id,
        data_source_ids=payload.data_source_ids,
        actor_id=admin.id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )


@router.delete("/{department_id}", status_code=204)
async def delete_department_endpoint(
    department_id: uuid.UUID,
    session: DbSession,
    admin: AdminUser,
    meta: Meta,
) -> Response:
    await delete_department(
        session,
        department_id=department_id,
        actor_id=admin.id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    return Response(status_code=204)
