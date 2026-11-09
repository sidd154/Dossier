from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import CurrentUser, DbSession, Meta
from app.auth.cookies import REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies
from app.auth.ratelimit import enforce_login_rate_limit, reset_login_rate_limit
from app.auth.schemas import ChangePasswordRequest, LoginRequest, TokenResponse
from app.auth.service import (
    AuthResult,
    authenticate,
    change_password,
    revoke_session,
    rotate_refresh_token,
)
from app.config import get_settings
from app.core.exceptions import AuthenticationError
from app.users.models import AppUser
from app.users.schemas import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


def _respond_with_tokens(response: Response, result: AuthResult) -> TokenResponse:
    settings = get_settings()
    refresh_max_age = settings.refresh_token_ttl_days * 24 * 60 * 60
    set_auth_cookies(
        response,
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        # The cookie outlives the JWT on purpose. The token inside still expires after
        # 15 minutes; the frontend exchanges the refresh token for a new one. A short
        # cookie lifetime would otherwise bounce active users back to /login mid-session.
        access_max_age=refresh_max_age,
        refresh_max_age=refresh_max_age,
        settings=settings,
    )
    return TokenResponse(
        access_token=result.access_token,
        expires_in=result.access_expires_in,
        user=UserRead.model_validate(result.user),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(enforce_login_rate_limit)],
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: DbSession,
    meta: Meta,
) -> TokenResponse:
    result = await authenticate(
        session,
        email=str(payload.email),
        password=payload.password,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    await reset_login_rate_limit(payload, request)
    return _respond_with_tokens(response, result)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    session: DbSession,
    meta: Meta,
) -> TokenResponse:
    try:
        result = await rotate_refresh_token(
            session,
            raw_token=request.cookies.get(REFRESH_COOKIE),
            ip=meta.ip,
            user_agent=meta.user_agent,
        )
    except AuthenticationError:
        clear_auth_cookies(response, get_settings())
        raise
    return _respond_with_tokens(response, result)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, session: DbSession) -> None:
    await revoke_session(session, raw_token=request.cookies.get(REFRESH_COOKIE))
    clear_auth_cookies(response, get_settings())
    response.status_code = 204


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser) -> AppUser:
    return user


@router.post("/change-password", response_model=TokenResponse)
async def change_own_password(
    payload: ChangePasswordRequest,
    response: Response,
    user: CurrentUser,
    session: DbSession,
    meta: Meta,
) -> TokenResponse:
    result = await change_password(
        session,
        user=user,
        current_password=payload.current_password,
        new_password=payload.new_password,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    return _respond_with_tokens(response, result)
