import uuid

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import AdminUser, DbSession, Meta, require_admin
from app.api.schemas import Page
from app.users.models import AccountStatus, UserRole
from app.users.schemas import (
    PasswordResetResponse,
    UserCreate,
    UserCreated,
    UserRead,
    UserUpdate,
)
from app.users.service import (
    create_user,
    disable_user,
    get_user,
    list_users,
    reset_password,
    update_user,
)

router = APIRouter(
    prefix="/users",
    tags=["admin:users"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=Page[UserRead])
async def list_users_endpoint(
    session: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    department_id: uuid.UUID | None = None,
    role: UserRole | None = None,
    status: AccountStatus | None = None,
) -> Page[UserRead]:
    items, total = await list_users(
        session,
        q=q,
        department_id=department_id,
        role=role,
        status=status,
        page=page,
        page_size=page_size,
    )
    return Page[UserRead](
        items=[UserRead.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=UserCreated, status_code=201)
async def create_user_endpoint(
    payload: UserCreate,
    session: DbSession,
    admin: AdminUser,
    meta: Meta,
) -> UserCreated:
    user, temporary_password = await create_user(
        session,
        payload=payload,
        actor_id=admin.id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    base = UserRead.model_validate(user).model_dump()
    return UserCreated(**base, temporary_password=temporary_password)


@router.get("/{user_id}", response_model=UserRead)
async def get_user_endpoint(user_id: uuid.UUID, session: DbSession) -> UserRead:
    return UserRead.model_validate(await get_user(session, user_id))


@router.patch("/{user_id}", response_model=UserRead)
async def update_user_endpoint(
    user_id: uuid.UUID,
    payload: UserUpdate,
    session: DbSession,
    admin: AdminUser,
    meta: Meta,
) -> UserRead:
    user = await update_user(
        session,
        user_id=user_id,
        payload=payload,
        actor_id=admin.id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    return UserRead.model_validate(user)


@router.delete("/{user_id}", status_code=204)
async def disable_user_endpoint(
    user_id: uuid.UUID,
    session: DbSession,
    admin: AdminUser,
    meta: Meta,
) -> Response:
    await disable_user(
        session,
        user_id=user_id,
        actor_id=admin.id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    return Response(status_code=204)


@router.post("/{user_id}/reset-password", response_model=PasswordResetResponse)
async def reset_password_endpoint(
    user_id: uuid.UUID,
    session: DbSession,
    admin: AdminUser,
    meta: Meta,
) -> PasswordResetResponse:
    temporary_password = await reset_password(
        session,
        user_id=user_id,
        actor_id=admin.id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    return PasswordResetResponse(temporary_password=temporary_password)
