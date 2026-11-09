import json
import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import ConnectorAuthError
from app.users.models import UserRole
from tests.conftest import login, make_user
from tests.fakes import FakeConnector

PAYLOAD = {
    "name": "Company Sheets",
    "type": "GOOGLE_SHEETS",
    "config": {"spreadsheet_id": "sheet-123"},
    "credentials": {
        "client_email": "service@example.iam.gserviceaccount.com",
        "private_key": "-----BEGIN PRIVATE KEY-----not-a-real-key",
    },
}


async def _as_admin(client: AsyncClient, session: AsyncSession) -> None:
    email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
    await make_user(session, email=email, role=UserRole.ADMIN)
    assert (await login(client, email)).status_code == 200


async def _create(client: AsyncClient, **overrides: object) -> dict:
    payload = {**PAYLOAD, **overrides}
    response = await client.post("/api/v1/admin/connectors", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_connector_never_returns_secrets(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)

    body = await _create(client)

    assert body["name"] == "Company Sheets"
    assert body["type"] == "GOOGLE_SHEETS"
    assert body["has_credentials"] is True
    serialised = json.dumps(body)
    assert "private_key" not in serialised
    assert "not-a-real-key" not in serialised


async def test_duplicate_name_is_rejected(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)
    await _create(client)

    response = await client.post("/api/v1/admin/connectors", json=PAYLOAD)

    assert response.status_code == 409
    assert response.json()["code"] == "name_in_use"


async def test_list_filters_by_type(client: AsyncClient, session: AsyncSession) -> None:
    await _as_admin(client, session)
    await _create(client)
    await _create(
        client,
        name="Company CRM",
        type="ZOHO_CRM",
        config={"api_domain": "https://www.zohoapis.com"},
        credentials={
            "client_id": "id",
            "client_secret": "secret",
            "refresh_token": "refresh",
        },
    )

    sheets = await client.get("/api/v1/admin/connectors?type=GOOGLE_SHEETS")
    crm = await client.get("/api/v1/admin/connectors?type=ZOHO_CRM")

    assert [item["name"] for item in sheets.json()["items"]] == ["Company Sheets"]
    assert [item["name"] for item in crm.json()["items"]] == ["Company CRM"]


async def test_update_connector_rotates_credentials(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)
    connector = await _create(client)

    response = await client.patch(
        f"/api/v1/admin/connectors/{connector['id']}",
        json={
            "config": {"spreadsheet_id": "sheet-999"},
            "credentials": {"client_email": "new@example.com", "private_key": "new"},
        },
    )

    assert response.status_code == 200
    assert response.json()["config"]["spreadsheet_id"] == "sheet-999"
    assert response.json()["has_credentials"] is True


async def test_validate_success_updates_timestamp(
    client: AsyncClient, session: AsyncSession, fake_connector: dict[str, object]
) -> None:
    await _as_admin(client, session)
    connector = await _create(client)

    response = await client.post(
        f"/api/v1/admin/connectors/{connector['id']}/validate"
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["last_validated_at"] is not None


async def test_validate_failure_is_reported_not_raised(
    client: AsyncClient, session: AsyncSession, fake_connector: dict[str, object]
) -> None:
    await _as_admin(client, session)
    connector = await _create(client)
    fake_connector["connector"] = FakeConnector(
        validate_error=ConnectorAuthError("Credentials expired")
    )

    response = await client.post(
        f"/api/v1/admin/connectors/{connector['id']}/validate"
    )

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["error"] == "Credentials expired"

    fetched = await client.get(f"/api/v1/admin/connectors/{connector['id']}")
    assert fetched.json()["last_validation_error"] == "Credentials expired"


async def test_list_assets(
    client: AsyncClient, session: AsyncSession, fake_connector: dict[str, object]
) -> None:
    await _as_admin(client, session)
    connector = await _create(client)

    response = await client.get(
        f"/api/v1/admin/connectors/{connector['id']}/assets"
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "external_id": "asset-1",
            "name": "Sheet One",
            "kind": "sheet",
            "config": {"sheet_title": "Sheet One"},
        }
    ]


async def test_delete_connector(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)
    connector = await _create(client)

    assert (
        await client.delete(f"/api/v1/admin/connectors/{connector['id']}")
    ).status_code == 204
    assert (
        await client.get(f"/api/v1/admin/connectors/{connector['id']}")
    ).status_code == 404


async def test_unknown_connector(client: AsyncClient, session: AsyncSession) -> None:
    await _as_admin(client, session)
    response = await client.get(f"/api/v1/admin/connectors/{uuid.uuid4()}")
    assert response.status_code == 404
