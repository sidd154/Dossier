import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import UserRole
from tests.conftest import login, make_department, make_user

ADMIN_GET_ROUTES = [
    "/api/v1/admin/users",
    "/api/v1/admin/departments",
    "/api/v1/admin/organisation",
    "/api/v1/admin/audit-logs",
    "/api/v1/admin/connectors",
    "/api/v1/admin/data-sources",
    "/api/v1/admin/sync-jobs",
    "/api/v1/admin/mail/settings",
    "/api/v1/admin/mail/templates",
    "/api/v1/admin/mail/schedules",
    "/api/v1/admin/mail/executions",
]


@pytest.mark.parametrize("path", ADMIN_GET_ROUTES)
async def test_unauthenticated_requests_are_rejected(
    raw_client: AsyncClient, path: str
) -> None:
    response = await raw_client.get(path)
    assert response.status_code == 401


@pytest.mark.parametrize("path", ADMIN_GET_ROUTES)
async def test_regular_users_cannot_read_admin_routes(
    client: AsyncClient, session: AsyncSession, path: str
) -> None:
    user = await make_user(session, email=f"user-{uuid.uuid4().hex[:8]}@example.com")
    assert (await login(client, user.email)).status_code == 200

    response = await client.get(path)

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


async def test_regular_users_cannot_mutate_admin_resources(
    client: AsyncClient, session: AsyncSession
) -> None:
    department = await make_department(session, name="Protected")
    user = await make_user(
        session, email=f"user-{uuid.uuid4().hex[:8]}@example.com", role=UserRole.USER
    )
    assert (await login(client, user.email)).status_code == 200

    create = await client.post("/api/v1/admin/departments", json={"name": "Nope"})
    assert create.status_code == 403

    patch = await client.patch(
        f"/api/v1/admin/departments/{department.id}", json={"name": "Hacked"}
    )
    assert patch.status_code == 403

    delete = await client.delete(f"/api/v1/admin/departments/{department.id}")
    assert delete.status_code == 403

    user_create = await client.post(
        "/api/v1/admin/users",
        json={
            "email": "escalate@example.com",
            "full_name": "Escalation",
            "department_id": str(department.id),
            "role": "ADMIN",
        },
    )
    assert user_create.status_code == 403


async def test_regular_users_can_read_their_own_profile(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await make_user(session, email=f"user-{uuid.uuid4().hex[:8]}@example.com")
    assert (await login(client, user.email)).status_code == 200

    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == user.email
