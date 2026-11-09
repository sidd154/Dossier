"""Shared request dependencies: session, identity, and authorisation."""

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.cookies import ACCESS_COOKIE
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import decode_access_token
from app.database.session import get_db
from app.permissions.context import PermissionContext, resolve_permission_context
from app.users.models import AccountStatus, AppUser, UserRole

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class RequestMeta:
    ip: str | None
    user_agent: str | None


def get_request_meta(request: Request) -> RequestMeta:
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else None
    if not ip and request.client:
        ip = request.client.host
    return RequestMeta(ip=ip, user_agent=request.headers.get("user-agent"))


DbSession = Annotated[AsyncSession, Depends(get_db)]
Meta = Annotated[RequestMeta, Depends(get_request_meta)]


async def get_current_user(
    request: Request,
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> AppUser:
    token = credentials.credentials if credentials else request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise AuthenticationError("Not authenticated")

    payload = decode_access_token(token)
    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("Invalid or expired token") from exc

    result = await session.execute(
        select(AppUser)
        .options(selectinload(AppUser.department))
        .where(AppUser.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None or user.status != AccountStatus.ACTIVE:
        raise AuthenticationError("Invalid or expired token")
    return user


CurrentUser = Annotated[AppUser, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> AppUser:
    if user.must_change_password:
        raise PermissionDeniedError(
            "You must change your password before continuing.",
            code="password_change_required",
        )
    if user.role != UserRole.ADMIN:
        raise PermissionDeniedError("Administrator access required.")
    return user


AdminUser = Annotated[AppUser, Depends(require_admin)]


async def get_permission_context(
    user: CurrentUser, session: DbSession
) -> PermissionContext:
    return await resolve_permission_context(session, user)


PermissionContextDep = Annotated[PermissionContext, Depends(get_permission_context)]
