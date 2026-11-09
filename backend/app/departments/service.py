"""Department CRUD and the delete-safety rule."""

import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit
from app.core.exceptions import ConflictError, NotFoundError
from app.core.text import slugify
from app.departments.models import Department
from app.departments.schemas import DepartmentCreate, DepartmentUpdate
from app.users.models import AppUser


def _snapshot(department: Department) -> dict[str, object]:
    return {
        "name": department.name,
        "slug": department.slug,
        "description": department.description,
        "is_active": department.is_active,
    }


async def list_departments(
    session: AsyncSession,
    *,
    q: str | None,
    is_active: bool | None,
    page: int,
    page_size: int,
) -> tuple[list[Department], int]:
    conditions: list[Any] = []
    if q:
        like = f"%{q.strip()}%"
        conditions.append(or_(Department.name.ilike(like), Department.slug.ilike(like)))
    if is_active is not None:
        conditions.append(Department.is_active.is_(is_active))

    count_stmt = select(func.count()).select_from(Department)
    list_stmt = select(Department)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
        list_stmt = list_stmt.where(*conditions)

    total = await session.scalar(count_stmt) or 0
    list_stmt = (
        list_stmt.order_by(Department.name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = (await session.execute(list_stmt)).scalars().all()
    return list(items), total


async def get_department(session: AsyncSession, department_id: uuid.UUID) -> Department:
    department = await session.get(Department, department_id)
    if department is None:
        raise NotFoundError("Department not found")
    return department


async def _unique_slug(session: AsyncSession, base: str) -> str:
    candidate = base
    suffix = 2
    while await session.scalar(select(Department.id).where(Department.slug == candidate)):
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


async def create_department(
    session: AsyncSession,
    *,
    payload: DepartmentCreate,
    actor_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> Department:
    name = payload.name.strip()
    existing = await session.scalar(select(Department.id).where(Department.name == name))
    if existing is not None:
        raise ConflictError("A department with this name already exists", code="name_in_use")

    department = Department(
        name=name,
        slug=await _unique_slug(session, slugify(name, fallback="department")),
        description=payload.description,
        is_active=payload.is_active,
    )
    session.add(department)
    await session.flush()

    await record_audit(
        session,
        actor_id=actor_id,
        action="department.created",
        entity_type="department",
        entity_id=str(department.id),
        after=_snapshot(department),
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    return department


async def update_department(
    session: AsyncSession,
    *,
    department_id: uuid.UUID,
    payload: DepartmentUpdate,
    actor_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> Department:
    department = await get_department(session, department_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return department

    if "name" in changes:
        new_name = str(changes["name"]).strip()
        clash = await session.scalar(
            select(Department.id).where(
                Department.name == new_name, Department.id != department.id
            )
        )
        if clash is not None:
            raise ConflictError(
                "A department with this name already exists", code="name_in_use"
            )
        changes["name"] = new_name

    before = _snapshot(department)
    for field, value in changes.items():
        setattr(department, field, value)
    await session.flush()

    await record_audit(
        session,
        actor_id=actor_id,
        action="department.updated",
        entity_type="department",
        entity_id=str(department.id),
        before=before,
        after=_snapshot(department),
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    return department


async def delete_department(
    session: AsyncSession,
    *,
    department_id: uuid.UUID,
    actor_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> None:
    department = await get_department(session, department_id)
    assigned = await session.scalar(
        select(func.count()).select_from(AppUser).where(AppUser.department_id == department.id)
    )
    if assigned:
        raise ConflictError(
            "Department still has users assigned; deactivate it instead.",
            code="department_in_use",
        )

    before = _snapshot(department)
    await session.delete(department)
    await record_audit(
        session,
        actor_id=actor_id,
        action="department.deleted",
        entity_type="department",
        entity_id=str(department_id),
        before=before,
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
