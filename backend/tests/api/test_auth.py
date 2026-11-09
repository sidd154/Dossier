import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.cookies import ACCESS_COOKIE, REFRESH_COOKIE
from app.users.models import AccountStatus, UserRole
from tests.conftest import DEFAULT_PASSWORD, login, make_user

NEW_PASSWORD = "A-Much-Better-Password-9"


async def test_login_returns_user_and_sets_cookies(
    client: AsyncClient, session: AsyncSession
) -> None:
    await make_user(session, email="login@example.com")

    response = await login(client, "login@example.com")

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "login@example.com"
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert client.cookies.get(ACCESS_COOKIE)
    assert client.cookies.get(REFRESH_COOKIE)


async def test_login_is_case_insensitive(client: AsyncClient, session: AsyncSession) -> None:
    await make_user(session, email="mixed@example.com")
    response = await login(client, "MIXED@Example.com")
    assert response.status_code == 200


async def test_wrong_password_is_rejected_without_enumeration(
    client: AsyncClient, session: AsyncSession
) -> None:
    await make_user(session, email="wrong@example.com")
    response = await login(client, "wrong@example.com", "definitely-not-it")

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"
    assert response.json()["detail"] == "Invalid email or password"


async def test_unknown_email_looks_identical(client: AsyncClient) -> None:
    response = await login(client, "nobody@example.com")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


async def test_disabled_user_cannot_log_in(
    client: AsyncClient, session: AsyncSession
) -> None:
    await make_user(session, email="disabled@example.com", status=AccountStatus.DISABLED)
    response = await login(client, "disabled@example.com")
    assert response.status_code == 401


async def test_me_requires_authentication(raw_client: AsyncClient) -> None:
    response = await raw_client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_returns_current_user(client: AsyncClient, session: AsyncSession) -> None:
    await make_user(session, email="me@example.com", role=UserRole.ADMIN)
    await login(client, "me@example.com")

    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"
    assert response.json()["department"]["name"]


async def test_refresh_rotates_and_detects_reuse(
    client: AsyncClient, session: AsyncSession, app
) -> None:
    await make_user(session, email="rotate@example.com")
    await login(client, "rotate@example.com")
    first_refresh = client.cookies.get(REFRESH_COOKIE)
    assert first_refresh

    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    second_refresh = client.cookies.get(REFRESH_COOKIE)
    assert second_refresh and second_refresh != first_refresh

    # Replaying a rotated token invalidates the whole family. Use fresh clients so the
    # cookie jar cannot send the newer token alongside the old one.
    async with AsyncClient(
        base_url="http://test", transport=ASGITransport(app=app)
    ) as replayer:
        replayer.cookies.set(
            REFRESH_COOKIE, first_refresh, domain="test", path="/api/v1/auth"
        )
        assert (await replayer.post("/api/v1/auth/refresh")).status_code == 401

    async with AsyncClient(
        base_url="http://test", transport=ASGITransport(app=app)
    ) as late:
        late.cookies.set(
            REFRESH_COOKIE, second_refresh, domain="test", path="/api/v1/auth"
        )
        assert (await late.post("/api/v1/auth/refresh")).status_code == 401


async def test_logout_revokes_the_session(
    client: AsyncClient, session: AsyncSession
) -> None:
    await make_user(session, email="logout@example.com")
    await login(client, "logout@example.com")
    refresh = client.cookies.get(REFRESH_COOKIE)

    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 204

    client.cookies.set(REFRESH_COOKIE, refresh, domain="test", path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_password_change_requires_current_password(
    client: AsyncClient, session: AsyncSession
) -> None:
    await make_user(session, email="change@example.com")
    await login(client, "change@example.com")

    response = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "not-the-password", "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 401


async def test_short_new_password_is_rejected(
    client: AsyncClient, session: AsyncSession
) -> None:
    await make_user(session, email="short@example.com")
    await login(client, "short@example.com")

    response = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "too-short"},
    )
    assert response.status_code == 422


async def test_password_change_swaps_credentials(
    client: AsyncClient, session: AsyncSession, app
) -> None:
    await make_user(session, email="swap@example.com")
    await login(client, "swap@example.com")

    response = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 200
    assert response.json()["user"]["must_change_password"] is False

    # The old credential is dead, the new one works in a fresh session.
    async with AsyncClient(
        base_url="http://test", transport=ASGITransport(app=app)
    ) as fresh:
        assert (await login(fresh, "swap@example.com", DEFAULT_PASSWORD)).status_code == 401
        assert (await login(fresh, "swap@example.com", NEW_PASSWORD)).status_code == 200


async def test_must_change_password_blocks_admin_access(
    client: AsyncClient, session: AsyncSession
) -> None:
    await make_user(
        session,
        email="temp@example.com",
        role=UserRole.ADMIN,
        must_change_password=True,
    )
    await login(client, "temp@example.com")

    response = await client.get("/api/v1/admin/users")
    assert response.status_code == 403
    assert response.json()["code"] == "password_change_required"


@pytest.mark.parametrize("email", ["not-an-email", ""])
async def test_invalid_login_payload(client: AsyncClient, email: str) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "whatever"}
    )
    assert response.status_code == 422
