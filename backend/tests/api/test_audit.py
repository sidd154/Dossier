import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import UserRole
from tests.conftest import login, make_department, make_user


async def _as_admin(client: AsyncClient, session: AsyncSession) -> None:
    email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
    await make_user(session, email=email, role=UserRole.ADMIN)
    assert (await login(client, email)).status_code == 200


async def test_department_mutations_are_audited(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)

    created = await client.post("/api/v1/admin/departments", json={"name": "Audited"})
    department_id = created.json()["id"]
    await client.patch(
        f"/api/v1/admin/departments/{department_id}", json={"description": "changed"}
    )

    response = await client.get("/api/v1/admin/audit-logs?entity_type=department")

    assert response.status_code == 200
    actions = [item["action"] for item in response.json()["items"]]
    assert "department.created" in actions
    assert "department.updated" in actions
    updated = next(
        item
        for item in response.json()["items"]
        if item["action"] == "department.updated"
    )
    assert updated["before"]["description"] is None
    assert updated["after"]["description"] == "changed"
    assert updated["actor_user_id"] is not None
    assert updated["ip"] == "127.0.0.1"


async def test_user_creation_is_audited(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)
    department = await make_department(session)

    await client.post(
        "/api/v1/admin/users",
        json={
            "email": "audited@example.com",
            "full_name": "Audited User",
            "department_id": str(department.id),
        },
    )

    response = await client.get("/api/v1/admin/audit-logs?action=user.created")
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["entity_type"] == "user"


async def test_pagination_does_not_lose_the_total(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)
    for index in range(3):
        await client.post(
            "/api/v1/admin/departments", json={"name": f"Paginated {index}"}
        )

    first = await client.get("/api/v1/admin/audit-logs?page=1&page_size=2")
    second = await client.get("/api/v1/admin/audit-logs?page=2&page_size=2")

    assert first.json()["total"] >= 3
    assert len(first.json()["items"]) == 2
    assert len(second.json()["items"]) >= 1
    assert first.json()["items"][0]["id"] != second.json()["items"][0]["id"]
