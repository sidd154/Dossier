import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import UserRole
from tests.conftest import login, make_organisation, make_user


async def _as_admin(client: AsyncClient, session: AsyncSession) -> None:
    email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
    await make_user(session, email=email, role=UserRole.ADMIN)
    assert (await login(client, email)).status_code == 200


async def test_missing_organisation_is_reported(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)
    response = await client.get("/api/v1/admin/organisation")
    assert response.status_code == 404


async def test_read_organisation(client: AsyncClient, session: AsyncSession) -> None:
    await _as_admin(client, session)
    await make_organisation(session, name="Acme Ltd")

    response = await client.get("/api/v1/admin/organisation")

    assert response.status_code == 200
    assert response.json()["name"] == "Acme Ltd"
    assert response.json()["timezone"] == "UTC"


async def test_update_organisation(client: AsyncClient, session: AsyncSession) -> None:
    await _as_admin(client, session)
    await make_organisation(session)

    response = await client.patch(
        "/api/v1/admin/organisation",
        json={
            "name": "Acme Holdings",
            "industry": "Software",
            "locations": ["London", "Lisbon"],
            "timezone": "Europe/London",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Acme Holdings"
    assert body["locations"] == ["London", "Lisbon"]
    assert body["timezone"] == "Europe/London"


async def test_unknown_timezone_is_rejected(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)
    await make_organisation(session)

    response = await client.patch(
        "/api/v1/admin/organisation", json={"timezone": "Mars/Olympus_Mons"}
    )
    assert response.status_code == 422


async def test_update_writes_an_audit_entry(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)
    await make_organisation(session)

    await client.patch("/api/v1/admin/organisation", json={"name": "Renamed"})

    logs = await client.get("/api/v1/admin/audit-logs?action=organisation.updated")
    assert logs.status_code == 200
    assert logs.json()["total"] == 1
    assert logs.json()["items"][0]["after"]["name"] == "Renamed"
