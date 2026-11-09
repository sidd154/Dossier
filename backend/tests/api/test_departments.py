import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import UserRole
from tests.conftest import login, make_department, make_user


async def _as_admin(client: AsyncClient, session: AsyncSession) -> None:
    email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
    await make_user(session, email=email, role=UserRole.ADMIN)
    assert (await login(client, email)).status_code == 200


async def test_create_and_fetch_department(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)

    created = await client.post(
        "/api/v1/admin/departments",
        json={"name": "Customer Success", "description": "Retention"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["slug"] == "customer-success"
    assert body["is_active"] is True

    fetched = await client.get(f"/api/v1/admin/departments/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Customer Success"


async def test_duplicate_name_is_case_insensitive(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)
    await client.post("/api/v1/admin/departments", json={"name": "Sales"})

    response = await client.post("/api/v1/admin/departments", json={"name": "sales"})

    assert response.status_code == 409
    assert response.json()["code"] == "name_in_use"


async def test_slug_collision_gets_a_suffix(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)
    first = await client.post("/api/v1/admin/departments", json={"name": "R and D"})
    second = await client.post("/api/v1/admin/departments", json={"name": "R & D"})

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["slug"] != second.json()["slug"]


async def test_list_filters(client: AsyncClient, session: AsyncSession) -> None:
    await _as_admin(client, session)
    await make_department(session, name="Active One")
    await make_department(session, name="Inactive One", is_active=False)

    active = await client.get("/api/v1/admin/departments?is_active=true")
    names = {item["name"] for item in active.json()["items"]}
    assert "Active One" in names
    assert "Inactive One" not in names

    searched = await client.get("/api/v1/admin/departments?q=inactive")
    assert [item["name"] for item in searched.json()["items"]] == ["Inactive One"]


async def test_update_department(client: AsyncClient, session: AsyncSession) -> None:
    await _as_admin(client, session)
    department = await make_department(session, name="Growth")

    response = await client.patch(
        f"/api/v1/admin/departments/{department.id}",
        json={"description": "Acquisition", "is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["description"] == "Acquisition"
    assert response.json()["is_active"] is False
    # The slug is an identifier and does not change when the display name does.
    assert response.json()["slug"] == department.slug


async def test_delete_empty_department(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)
    department = await make_department(session, name="Temporary")

    assert (await client.delete(f"/api/v1/admin/departments/{department.id}")).status_code == 204
    assert (await client.get(f"/api/v1/admin/departments/{department.id}")).status_code == 404


async def test_department_with_users_cannot_be_deleted(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)
    department = await make_department(session, name="Staffed")
    await make_user(session, email="member@example.com", department=department)

    response = await client.delete(f"/api/v1/admin/departments/{department.id}")

    assert response.status_code == 409
    assert response.json()["code"] == "department_in_use"


async def test_unknown_department(client: AsyncClient, session: AsyncSession) -> None:
    await _as_admin(client, session)
    assert (await client.get(f"/api/v1/admin/departments/{uuid.uuid4()}")).status_code == 404


async def test_blank_name_is_rejected(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)
    response = await client.post("/api/v1/admin/departments", json={"name": ""})
    assert response.status_code == 422
