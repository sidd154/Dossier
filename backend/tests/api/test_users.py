import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import UserRole
from tests.conftest import DEFAULT_PASSWORD, login, make_department, make_user


async def _as_admin(client: AsyncClient, session: AsyncSession, email: str | None = None):
    email = email or f"admin-{uuid.uuid4().hex[:8]}@example.com"
    admin = await make_user(session, email=email, role=UserRole.ADMIN)
    response = await login(client, email)
    assert response.status_code == 200
    return admin


async def test_create_user_returns_a_temporary_password(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)
    department = await make_department(session, name="Marketing")

    response = await client.post(
        "/api/v1/admin/users",
        json={
            "email": "new@example.com",
            "full_name": "New Person",
            "department_id": str(department.id),
            "role": "USER",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new@example.com"
    assert body["must_change_password"] is True
    assert body["status"] == "ACTIVE"
    assert len(body["temporary_password"]) == 16


async def test_temporary_password_logs_in_and_demands_change(
    client: AsyncClient, session: AsyncSession, app
) -> None:
    await _as_admin(client, session)
    department = await make_department(session, name="Operations")
    created = await client.post(
        "/api/v1/admin/users",
        json={
            "email": "temp@example.com",
            "full_name": "Temp Person",
            "department_id": str(department.id),
        },
    )
    temporary_password = created.json()["temporary_password"]

    async with AsyncClient(
        base_url="http://test", transport=ASGITransport(app=app)
    ) as fresh:
        response = await login(fresh, "temp@example.com", temporary_password)
        assert response.status_code == 200
        assert response.json()["user"]["must_change_password"] is True


async def test_duplicate_email_is_rejected(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)
    department = await make_department(session)
    payload = {
        "email": "dupe@example.com",
        "full_name": "Dupe",
        "department_id": str(department.id),
    }
    assert (await client.post("/api/v1/admin/users", json=payload)).status_code == 201

    response = await client.post("/api/v1/admin/users", json=payload)
    assert response.status_code == 409
    assert response.json()["code"] == "email_in_use"


async def test_unknown_department_is_rejected(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)
    response = await client.post(
        "/api/v1/admin/users",
        json={
            "email": "nodep@example.com",
            "full_name": "No Department",
            "department_id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 404


async def test_inactive_department_is_rejected(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)
    department = await make_department(session, name="Closed", is_active=False)
    response = await client.post(
        "/api/v1/admin/users",
        json={
            "email": "closed@example.com",
            "full_name": "Closed Dept",
            "department_id": str(department.id),
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "department_inactive"


async def test_list_filters_by_role_and_department(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)
    sales = await make_department(session, name="Sales North")
    finance = await make_department(session, name="Finance")
    await make_user(session, email="sales@example.com", department=sales)
    await make_user(session, email="finance@example.com", department=finance)
    await make_user(
        session, email="boss@example.com", department=sales, role=UserRole.ADMIN
    )

    by_department = await client.get(
        f"/api/v1/admin/users?department_id={sales.id}"
    )
    assert by_department.status_code == 200
    emails = {item["email"] for item in by_department.json()["items"]}
    assert {"sales@example.com", "boss@example.com"} <= emails
    assert "finance@example.com" not in emails

    by_role = await client.get("/api/v1/admin/users?role=ADMIN")
    assert all(item["role"] == "ADMIN" for item in by_role.json()["items"])

    search = await client.get("/api/v1/admin/users?q=finance@")
    assert [item["email"] for item in search.json()["items"]] == ["finance@example.com"]


async def test_update_user_role_and_department(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)
    old_department = await make_department(session, name="Old")
    new_department = await make_department(session, name="New")
    user = await make_user(session, email="move@example.com", department=old_department)

    response = await client.patch(
        f"/api/v1/admin/users/{user.id}",
        json={"department_id": str(new_department.id), "role": "ADMIN"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "ADMIN"
    assert response.json()["department"]["name"] == "New"


async def test_last_admin_cannot_be_demoted_disabled_or_deleted(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await _as_admin(client, session)

    demote = await client.patch(
        f"/api/v1/admin/users/{admin.id}", json={"role": "USER"}
    )
    assert demote.status_code == 409
    assert demote.json()["code"] == "last_admin"

    disable = await client.patch(
        f"/api/v1/admin/users/{admin.id}", json={"status": "DISABLED"}
    )
    assert disable.status_code == 409

    delete = await client.delete(f"/api/v1/admin/users/{admin.id}")
    assert delete.status_code == 409


async def test_admin_can_be_removed_when_another_exists(
    client: AsyncClient, session: AsyncSession
) -> None:
    first = await _as_admin(client, session)
    second = await make_user(session, email="second-admin@example.com", role=UserRole.ADMIN)

    response = await client.patch(
        f"/api/v1/admin/users/{second.id}", json={"status": "DISABLED"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "DISABLED"
    assert first.id != second.id


async def test_reset_password_returns_a_new_temporary_password(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)
    department = await make_department(session)
    user = await make_user(session, email="reset@example.com", department=department)

    response = await client.post(f"/api/v1/admin/users/{user.id}/reset-password")

    assert response.status_code == 200
    temporary_password = response.json()["temporary_password"]
    assert len(temporary_password) == 16
    assert temporary_password != DEFAULT_PASSWORD


async def test_disabling_a_user_invalidates_their_access_immediately(
    client: AsyncClient, session: AsyncSession, app
) -> None:
    await _as_admin(client, session)
    department = await make_department(session)
    user = await make_user(session, email="victim@example.com", department=department)

    async with AsyncClient(
        base_url="http://test", transport=ASGITransport(app=app)
    ) as victim:
        assert (await login(victim, "victim@example.com")).status_code == 200
        assert (await victim.get("/api/v1/auth/me")).status_code == 200

        disabled = await client.delete(f"/api/v1/admin/users/{user.id}")
        assert disabled.status_code == 204

        assert (await victim.get("/api/v1/auth/me")).status_code == 401


async def test_delete_is_a_soft_disable(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)
    department = await make_department(session)
    user = await make_user(session, email="soft@example.com", department=department)

    assert (await client.delete(f"/api/v1/admin/users/{user.id}")).status_code == 204

    fetched = await client.get(f"/api/v1/admin/users/{user.id}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "DISABLED"


async def test_get_unknown_user(client: AsyncClient, session: AsyncSession) -> None:
    await _as_admin(client, session)
    response = await client.get(f"/api/v1/admin/users/{uuid.uuid4()}")
    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {
            "email": "bad",
            "full_name": "X",
            "department_id": "00000000-0000-0000-0000-000000000001",
        },
        {
            "email": "a@b.com",
            "full_name": "A",
            "department_id": "00000000-0000-0000-0000-000000000001",
        },
    ],
)
async def test_invalid_create_payloads(
    client: AsyncClient, session: AsyncSession, payload: dict
) -> None:
    await _as_admin(client, session)
    response = await client.post("/api/v1/admin/users", json=payload)
    assert response.status_code == 422
