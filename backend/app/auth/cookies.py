"""Cookie names and helpers.

Both tokens are httpOnly: JavaScript never sees them, and server components read the
access token to call the API on the user's behalf. The Next.js rewrite proxy keeps the
browser same-origin so ``SameSite=Lax`` is sufficient.
"""

from fastapi import Response

from app.config import Settings

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    access_max_age: int,
    refresh_max_age: int,
    settings: Settings,
) -> None:
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=access_max_age,
        path="/",
        httponly=True,
        secure=settings.allow_secure_cookies,
        samesite="lax",
        domain=settings.cookie_domain,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=refresh_max_age,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.allow_secure_cookies,
        samesite="lax",
        domain=settings.cookie_domain,
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        ACCESS_COOKIE,
        path="/",
        httponly=True,
        secure=settings.allow_secure_cookies,
        samesite="lax",
        domain=settings.cookie_domain,
    )
    response.delete_cookie(
        REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.allow_secure_cookies,
        samesite="lax",
        domain=settings.cookie_domain,
    )
