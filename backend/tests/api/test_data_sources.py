import uuid

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import ConnectorFetchError, FetchedTable
from app.data_sources.models import DataSource
from app.permissions.context import resolve_allowed_source_ids
from app.snapshots.models import SnapshotRecord
from app.users.models import UserRole
from tests.conftest import login, make_user
from tests.fakes import FakeConnector

CONNECTOR = {
    "name": "Sheets",
    "type": "GOOGLE_SHEETS",
    "config": {"spreadsheet_id": "sheet-123"},
    "credentials": {"client_email": "svc@example.com", "private_key": "key"},
}


async def _setup(client: AsyncClient, session: AsyncSession) -> tuple[str, str]:
    """Returns (connector_id, department_id) with an authenticated admin."""
    email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
    admin = await make_user(session, email=email, role=UserRole.ADMIN)
    assert (await login(client, email)).status_code == 200

    connector = await client.post("/api/v1/admin/connectors", json=CONNECTOR)
    assert connector.status_code == 201, connector.text
    return connector.json()["id"], str(admin.department_id)


async def _create_source(client: AsyncClient, connector_id: str, name: str = "Sheet One") -> dict:
    response = await client.post(
        "/api/v1/admin/data-sources",
        json={
            "connector_id": connector_id,
            "external_id": "asset-1",
            "name": name,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_source_from_asset(
    client: AsyncClient, session: AsyncSession, fake_connector: dict[str, object]
) -> None:
    connector_id, _ = await _setup(client, session)

    body = await _create_source(client, connector_id)

    assert body["connector_id"] == connector_id
    assert body["connector_name"] == "Sheets"
    assert body["kind"] == "sheet"
    assert body["current_snapshot"] is None


async def test_unknown_asset_is_rejected(
    client: AsyncClient, session: AsyncSession, fake_connector: dict[str, object]
) -> None:
    connector_id, _ = await _setup(client, session)

    response = await client.post(
        "/api/v1/admin/data-sources",
        json={"connector_id": connector_id, "external_id": "missing"},
    )

    assert response.status_code == 404


async def test_duplicate_source_is_rejected(
    client: AsyncClient, session: AsyncSession, fake_connector: dict[str, object]
) -> None:
    connector_id, _ = await _setup(client, session)
    await _create_source(client, connector_id)

    response = await client.post(
        "/api/v1/admin/data-sources",
        json={"connector_id": connector_id, "external_id": "asset-1"},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "source_exists"


async def test_successful_sync_creates_and_promotes_snapshot(
    client: AsyncClient, session: AsyncSession, fake_connector: dict[str, object]
) -> None:
    connector_id, _ = await _setup(client, session)
    source = await _create_source(client, connector_id)

    response = await client.post(f"/api/v1/admin/data-sources/{source['id']}/sync")

    assert response.status_code == 200
    job = response.json()
    assert job["status"] == "SUCCEEDED"
    assert job["record_count"] == 2
    assert job["trigger"] == "MANUAL"
    assert job["snapshot_id"]

    fetched = await client.get(f"/api/v1/admin/data-sources/{source['id']}")
    assert fetched.json()["current_snapshot"]["record_count"] == 2
    assert fetched.json()["schema_hash"]

    stored = await session.scalar(
        select(func.count())
        .select_from(SnapshotRecord)
        .where(SnapshotRecord.snapshot_id == uuid.UUID(job["snapshot_id"]))
    )
    assert stored == 2


async def test_failed_sync_keeps_the_previous_snapshot(
    client: AsyncClient, session: AsyncSession, fake_connector: dict[str, object]
) -> None:
    connector_id, _ = await _setup(client, session)
    source = await _create_source(client, connector_id)

    first = await client.post(f"/api/v1/admin/data-sources/{source['id']}/sync")
    first_snapshot = first.json()["snapshot_id"]

    fake_connector["connector"] = FakeConnector(
        error=ConnectorFetchError("Sheets unavailable")
    )
    second = await client.post(f"/api/v1/admin/data-sources/{source['id']}/sync")

    assert second.status_code == 200
    assert second.json()["status"] == "FAILED"
    assert second.json()["error"] == "Sheets unavailable"

    fetched = await client.get(f"/api/v1/admin/data-sources/{source['id']}")
    assert fetched.json()["current_snapshot"]["id"] == first_snapshot

    history = await client.get(
        f"/api/v1/admin/data-sources/{source['id']}/snapshots"
    )
    assert history.json()["total"] == 1


async def test_partial_sync_is_marked_partial(
    client: AsyncClient, session: AsyncSession, fake_connector: dict[str, object]
) -> None:
    connector_id, _ = await _setup(client, session)
    source = await _create_source(client, connector_id)
    fake_connector["connector"] = FakeConnector(
        table=FetchedTable(columns=["id"], rows=[{"id": "1"}], partial=True)
    )

    response = await client.post(f"/api/v1/admin/data-sources/{source['id']}/sync")

    assert response.json()["status"] == "PARTIAL"
    history = await client.get(
        f"/api/v1/admin/data-sources/{source['id']}/snapshots"
    )
    assert history.json()["items"][0]["status"] == "PARTIAL"


async def test_snapshots_and_jobs_are_listed(
    client: AsyncClient, session: AsyncSession, fake_connector: dict[str, object]
) -> None:
    connector_id, _ = await _setup(client, session)
    source = await _create_source(client, connector_id)
    await client.post(f"/api/v1/admin/data-sources/{source['id']}/sync")

    snapshots = await client.get(
        f"/api/v1/admin/data-sources/{source['id']}/snapshots"
    )
    jobs = await client.get("/api/v1/admin/sync-jobs")

    assert snapshots.json()["total"] == 1
    assert jobs.json()["total"] == 1
    assert jobs.json()["items"][0]["status"] == "SUCCEEDED"


async def test_department_grants_control_resolution(
    client: AsyncClient, session: AsyncSession, fake_connector: dict[str, object]
) -> None:
    connector_id, department_id = await _setup(client, session)
    source = await _create_source(client, connector_id)

    listing = await client.get(
        f"/api/v1/admin/departments/{department_id}/sources"
    )
    assert listing.status_code == 200
    assert listing.json()["entries"][0]["granted"] is False
    assert await resolve_allowed_source_ids(session, uuid.UUID(department_id)) == frozenset()

    granted = await client.put(
        f"/api/v1/admin/departments/{department_id}/sources",
        json={"data_source_ids": [source["id"]]},
    )
    assert granted.status_code == 200
    assert granted.json()["entries"][0]["granted"] is True

    allowed = await resolve_allowed_source_ids(session, uuid.UUID(department_id))
    assert allowed == frozenset({uuid.UUID(source["id"])})

    # Deactivating the source removes it from the allowed set even though the grant stays.
    await client.patch(
        f"/api/v1/admin/data-sources/{source['id']}", json={"is_active": False}
    )
    assert await resolve_allowed_source_ids(session, uuid.UUID(department_id)) == frozenset()

    # Emptying the grant set is fail-closed, not "everything".
    await client.put(
        f"/api/v1/admin/departments/{department_id}/sources",
        json={"data_source_ids": []},
    )
    assert await resolve_allowed_source_ids(session, uuid.UUID(department_id)) == frozenset()


async def test_unknown_source_is_rejected_for_grants(
    client: AsyncClient, session: AsyncSession
) -> None:
    _, department_id = await _setup(client, session)

    response = await client.put(
        f"/api/v1/admin/departments/{department_id}/sources",
        json={"data_source_ids": [str(uuid.uuid4())]},
    )

    assert response.status_code == 404


async def test_source_rows_are_persisted(
    client: AsyncClient, session: AsyncSession, fake_connector: dict[str, object]
) -> None:
    connector_id, _ = await _setup(client, session)
    await _create_source(client, connector_id)

    total = await session.scalar(select(func.count()).select_from(DataSource))
    assert total == 1
