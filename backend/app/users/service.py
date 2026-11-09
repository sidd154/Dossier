"""User management and the invariant that an active administrator always remains."""

import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit.service import record_audit
from app.auth.service import revoke_all_user_tokens
from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import generate_temporary_password, hash_password
from app.departments.models import Department
from app.users.models import AccountStatus, AppUser, UserRole
from app.users.schemas import UserCreate, UserUpdate


def _snapshot(user: AppUser) -> dict[str, object]:
    return {
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "status": user.status.value,
        "department_id": str(user.department_id),
    }


async def list_users(
    session: AsyncSession,
    *,
    q: str | None,
    department_id: uuid.UUID | None,
    role: UserRole | None,
    status: AccountStatus | None,
    page: int,
    page_size: int,
) -> tuple[list[AppUser], int]:
    conditions: list[Any] = []
    if q:
        like = f"%{q.strip()}%"
        conditions.append(or_(AppUser.email.ilike(like), AppUser.full_name.ilike(like)))
    if department_id is not None:
        conditions.append(AppUser.department_id == department_id)
    if role is not None:
        conditions.append(AppUser.role == role)
    if status is not None:
        conditions.append(AppUser.status == status)

    count_stmt = select(func.count()).select_from(AppUser)
    list_stmt = select(AppUser).options(selectinload(AppUser.department))
    if conditions:
        count_stmt = count_stmt.where(*conditions)
        list_stmt = list_stmt.where(*conditions)

    total = await session.scalar(count_stmt) or 0
    list_stmt = (
        list_stmt.order_by(AppUser.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = (await session.execute(list_stmt)).scalars().all()
    return list(items), total


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> AppUser:
    result = await session.execute(
        select(AppUser)
        .options(selectinload(AppUser.department))
        .where(AppUser.id == user_id)
        # The same identity-mapped object may still hold an old department reference
        # after an update; force the row and its eager loads to be re-read.
        .execution_options(populate_existing=True)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError("User not found")
    return user


async def _require_assignable_department(
    session: AsyncSession, department_id: uuid.UUID
) -> Department:
    department = await session.get(Department, department_id)
    if department is None:
        raise NotFoundError("Department not found")
    if not department.is_active:
        raise ConflictError(
            "Cannot assign a user to an inactive department", code="department_inactive"
        )
    return department


async def create_user(
    session: AsyncSession,
    *,
    payload: UserCreate,
    actor_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> tuple[AppUser, str]:
    email = str(payload.email).strip().lower()
    existing = await session.scalar(select(AppUser.id).where(AppUser.email == email))
    if existing is not None:
        raise ConflictError("Email already in use", code="email_in_use")

    await _require_assignable_department(session, payload.department_id)

    temporary_password = generate_temporary_password()
    user = AppUser(
        email=email,
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(temporary_password),
        role=payload.role,
        status=AccountStatus.ACTIVE,
        department_id=payload.department_id,
        must_change_password=True,
    )
    session.add(user)
    await session.flush()

    await record_audit(
        session,
        actor_id=actor_id,
        action="user.created",
        entity_type="user",
        entity_id=str(user.id),
        after=_snapshot(user),
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    return await get_user(session, user.id), temporary_password


async def _guard_last_admin(
    session: AsyncSession,
    user: AppUser,
    *,
    new_role: UserRole,
    new_status: AccountStatus,
) -> None:
    currently_admin = user.role == UserRole.ADMIN and user.status == AccountStatus.ACTIVE
    will_remain_admin = (
        new_role == UserRole.ADMIN and new_status == AccountStatus.ACTIVE
    )
    if not currently_admin or will_remain_admin:
        return

    # Lock every active admin row so two concurrent demotions cannot both succeed.
    admin_ids = (
        await session.execute(
            select(AppUser.id)
            .where(AppUser.role == UserRole.ADMIN, AppUser.status == AccountStatus.ACTIVE)
            .with_for_update()
        )
    ).scalars().all()
    if len(admin_ids) <= 1:
        raise ConflictError(
            "At least one active administrator must remain", code="last_admin"
        )


async def update_user(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    payload: UserUpdate,
    actor_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> AppUser:
    user = await get_user(session, user_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return user

    if "department_id" in changes:
        await _require_assignable_department(session, changes["department_id"])
    if "full_name" in changes:
        changes["full_name"] = str(changes["full_name"]).strip()

    if "role" in changes or "status" in changes:
        await _guard_last_admin(
            session,
            user,
            new_role=changes.get("role", user.role),
            new_status=changes.get("status", user.status),
        )

    before = _snapshot(user)
    for field, value in changes.items():
        setattr(user, field, value)

    disabled = changes.get("status") == AccountStatus.DISABLED
    if disabled:
        await revoke_all_user_tokens(session, user.id)

    await session.flush()
    await record_audit(
        session,
        actor_id=actor_id,
        action="user.disabled" if disabled else "user.updated",
        entity_type="user",
        entity_id=str(user.id),
        before=before,
        after=_snapshot(user),
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    return await get_user(session, user.id)


async def disable_user(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    actor_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> None:
    await update_user(
        session,
        user_id=user_id,
        payload=UserUpdate(status=AccountStatus.DISABLED),
        actor_id=actor_id,
        ip=ip,
        user_agent=user_agent,
    )


async def reset_password(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    actor_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> str:
    user = await get_user(session, user_id)
    temporary_password = generate_temporary_password()
    user.hashed_password = hash_password(temporary_password)
    user.must_change_password = True
    await revoke_all_user_tokens(session, user.id)

    await record_audit(
        session,
        actor_id=actor_id,
        action="user.password_reset",
        entity_type="user",
        entity_id=str(user.id),
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    return temporary_password
