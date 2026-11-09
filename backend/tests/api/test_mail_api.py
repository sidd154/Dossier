import smtplib
import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.mail.models import MailExecution, MailTrigger
from app.users.models import UserRole
from app.workers.tasks import execute_mail_execution
from tests.conftest import (
    login,
    make_department,
    make_organisation,
    make_source_snapshot,
    make_user,
)

SETTINGS_PAYLOAD = {
    "host": "smtp.example.com",
    "port": 587,
    "username": "mailer",
    "from_email": "noreply@example.com",
    "from_name": "Dossier",
    "security": "STARTTLS",
    "password": "very-secret-password",
}


async def _as_admin(
    client: AsyncClient, session: AsyncSession, *, with_org: bool = True
) -> None:
    email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
    await make_user(session, email=email, role=UserRole.ADMIN)
    if with_org:
        await make_organisation(session)
    assert (await login(client, email)).status_code == 200


async def _mail_fixture(client: AsyncClient, session: AsyncSession) -> dict:
    await _as_admin(client, session)
    sales = await make_department(session, name="Sales")
    finance = await make_department(session, name="Finance")
    sales_source = await make_source_snapshot(
        session,
        name="Sales Data",
        rows=[{"Deal": "Alpha", "Amount": 100}],
        department=sales,
    )
    finance_source = await make_source_snapshot(
        session,
        name="Finance Data",
        rows=[{"Account": "Secret Fund", "Balance": 9999}],
        department=finance,
    )
    template = await client.post(
        "/api/v1/admin/mail/templates",
        json={
            "name": f"Brief {uuid.uuid4().hex[:6]}",
            "subject_template": "{{ department.name }} brief",
            "system_prompt": "Summarise the numbers for the team.",
        },
    )
    assert template.status_code == 201, template.text
    return {
        "sales": sales,
        "finance": finance,
        "sales_source": sales_source,
        "finance_source": finance_source,
        "template": template.json(),
    }


# ------------------------------------------------------------------ settings


async def test_settings_are_unconfigured_initially(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)
    assert (await client.get("/api/v1/admin/mail/settings")).status_code == 404


async def test_settings_update_never_returns_the_password(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)

    response = await client.patch(
        "/api/v1/admin/mail/settings", json=SETTINGS_PAYLOAD
    )

    assert response.status_code == 200
    body = response.json()
    assert body["has_password"] is True
    assert body["host"] == "smtp.example.com"
    assert "very-secret-password" not in response.text

    fetched = await client.get("/api/v1/admin/mail/settings")
    assert fetched.json()["has_password"] is True


async def test_settings_require_host_and_sender(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)
    response = await client.patch(
        "/api/v1/admin/mail/settings", json={"port": 25}
    )
    assert response.status_code == 409
    assert response.json()["code"] == "smtp_incomplete"


async def test_settings_password_can_be_cleared(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _as_admin(client, session)
    await client.patch("/api/v1/admin/mail/settings", json=SETTINGS_PAYLOAD)

    response = await client.patch(
        "/api/v1/admin/mail/settings", json={"clear_password": True}
    )

    assert response.status_code == 200
    assert response.json()["has_password"] is False


async def test_test_send_succeeds_with_capture(
    client: AsyncClient, session: AsyncSession, fake_smtp: list
) -> None:
    await _as_admin(client, session)
    await client.patch("/api/v1/admin/mail/settings", json=SETTINGS_PAYLOAD)

    response = await client.post(
        "/api/v1/admin/mail/settings/test", json={"to": "ops@example.com"}
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert len(fake_smtp) == 1
    assert str(fake_smtp[0]["To"]) == "ops@example.com"


async def test_test_send_reports_transport_failure(
    client: AsyncClient, session: AsyncSession, monkeypatch
) -> None:
    await _as_admin(client, session)
    await client.patch("/api/v1/admin/mail/settings", json=SETTINGS_PAYLOAD)

    def boom(*_args: object, **_kwargs: object) -> None:
        raise smtplib.SMTPException("connection refused")

    monkeypatch.setattr("app.mail.sender._send_sync", boom)

    response = await client.post(
        "/api/v1/admin/mail/settings/test", json={"to": "ops@example.com"}
    )

    assert response.status_code == 200
    assert response.json()["ok"] is False
    fetched = await client.get("/api/v1/admin/mail/settings")
    assert "connection refused" in (fetched.json()["last_test_error"] or "")


# ------------------------------------------------------------------ templates


async def test_template_crud(
    client: AsyncClient, session: AsyncSession
) -> None:
    data = await _mail_fixture(client, session)
    template_id = data["template"]["id"]

    listed = await client.get("/api/v1/admin/mail/templates")
    assert listed.json()["total"] == 1

    fetched = await client.get(f"/api/v1/admin/mail/templates/{template_id}")
    assert fetched.status_code == 200

    updated = await client.patch(
        f"/api/v1/admin/mail/templates/{template_id}",
        json={"description": "Updated"},
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Updated"


async def test_duplicate_template_name_is_rejected(
    client: AsyncClient, session: AsyncSession
) -> None:
    data = await _mail_fixture(client, session)
    response = await client.post(
        "/api/v1/admin/mail/templates",
        json={
            "name": data["template"]["name"],
            "subject_template": "Subject",
            "system_prompt": "Prompt",
        },
    )
    assert response.status_code == 409


async def test_preview_uses_only_permitted_sources(
    client: AsyncClient,
    session: AsyncSession,
    fake_llm,
) -> None:
    data = await _mail_fixture(client, session)

    response = await client.post(
        f"/api/v1/admin/mail/templates/{data['template']['id']}/preview",
        json={
            "department_id": str(data["sales"].id),
            "source_ids": [
                str(data["sales_source"].id),
                str(data["finance_source"].id),
            ],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sources_used"] == ["Sales Data"]
    assert body["sources_excluded"] == ["Finance Data"]
    assert "Generated summary body." in body["body"]
    assert body["body"].startswith("Hello Sample Recipient,")

    prompt = fake_llm.prompts[0]
    assert "Sales Data" in prompt
    assert "Finance Data" not in prompt
    assert "Secret Fund" not in prompt


async def test_preview_rejects_a_department_with_no_access(
    client: AsyncClient, session: AsyncSession, fake_llm
) -> None:
    data = await _mail_fixture(client, session)

    response = await client.post(
        f"/api/v1/admin/mail/templates/{data['template']['id']}/preview",
        json={
            "department_id": str(data["sales"].id),
            "source_ids": [str(data["finance_source"].id)],
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "no_permitted_sources"
    assert fake_llm.calls == []


async def test_test_send_uses_the_generated_body(
    client: AsyncClient,
    session: AsyncSession,
    fake_llm,
    fake_smtp: list,
) -> None:
    data = await _mail_fixture(client, session)
    await client.patch("/api/v1/admin/mail/settings", json=SETTINGS_PAYLOAD)

    response = await client.post(
        f"/api/v1/admin/mail/templates/{data['template']['id']}/test-send",
        json={
            "to": "reviewer@example.com",
            "department_id": str(data["sales"].id),
            "source_ids": [str(data["sales_source"].id)],
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True
    assert len(fake_smtp) == 1
    message = fake_smtp[0]
    assert str(message["To"]) == "reviewer@example.com"
    assert "Generated summary body." in message.get_content()


async def test_template_in_use_cannot_be_deleted(
    client: AsyncClient, session: AsyncSession
) -> None:
    data = await _mail_fixture(client, session)
    created = await _create_schedule(
        client, data, name=f"S {uuid.uuid4().hex[:6]}"
    )
    assert created.status_code == 201

    response = await client.delete(
        f"/api/v1/admin/mail/templates/{data['template']['id']}"
    )
    assert response.status_code == 409
    assert response.json()["code"] == "template_in_use"


# ------------------------------------------------------------------ schedules


async def _create_schedule(
    client: AsyncClient, data: dict, *, name: str, **overrides
):
    payload = {
        "name": name,
        "template_id": data["template"]["id"],
        "enabled": True,
        "frequency": "DAILY",
        "time_of_day": "09:00:00",
        "timezone": "UTC",
        "row_limit": 10,
        "source_ids": [str(data["sales_source"].id)],
        "department_id": str(data["sales"].id),
    }
    payload.update(overrides)
    return await client.post("/api/v1/admin/mail/schedules", json=payload)


async def test_schedule_create_computes_next_run(
    client: AsyncClient, session: AsyncSession
) -> None:
    data = await _mail_fixture(client, session)

    response = await _create_schedule(
        client, data, name=f"Daily {uuid.uuid4().hex[:6]}"
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["next_run_at"] is not None
    assert body["template_name"] == data["template"]["name"]
    assert body["source_names"] == ["Sales Data"]
    assert body["department_name"] == "Sales"


async def test_weekly_schedule_requires_a_weekday(
    client: AsyncClient, session: AsyncSession
) -> None:
    data = await _mail_fixture(client, session)
    response = await _create_schedule(
        client,
        data,
        name=f"Weekly {uuid.uuid4().hex[:6]}",
        frequency="WEEKLY",
    )
    assert response.status_code == 409
    assert response.json()["code"] == "invalid_schedule"


async def test_monthly_schedule_requires_a_day(
    client: AsyncClient, session: AsyncSession
) -> None:
    data = await _mail_fixture(client, session)
    response = await _create_schedule(
        client,
        data,
        name=f"Monthly {uuid.uuid4().hex[:6]}",
        frequency="MONTHLY",
    )
    assert response.status_code == 409
    assert response.json()["code"] == "invalid_schedule"


async def test_schedule_requires_a_known_department(
    client: AsyncClient, session: AsyncSession
) -> None:
    data = await _mail_fixture(client, session)
    response = await _create_schedule(
        client,
        data,
        name=f"Nowhere {uuid.uuid4().hex[:6]}",
        department_id=str(uuid.uuid4()),
    )
    assert response.status_code == 404


async def test_schedule_rejects_unknown_timezone(
    client: AsyncClient, session: AsyncSession
) -> None:
    data = await _mail_fixture(client, session)
    response = await _create_schedule(
        client,
        data,
        name=f"TZ {uuid.uuid4().hex[:6]}",
        timezone="Mars/Olympus",
    )
    assert response.status_code == 409
    assert response.json()["code"] == "invalid_timezone"


async def test_disabling_a_schedule_clears_next_run(
    client: AsyncClient, session: AsyncSession
) -> None:
    data = await _mail_fixture(client, session)
    created = await _create_schedule(
        client, data, name=f"Toggle {uuid.uuid4().hex[:6]}"
    )
    schedule_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/admin/mail/schedules/{schedule_id}", json={"enabled": False}
    )

    assert response.status_code == 200
    assert response.json()["next_run_at"] is None


async def test_run_endpoint_creates_a_manual_execution(
    client: AsyncClient, session: AsyncSession, monkeypatch
) -> None:
    data = await _mail_fixture(client, session)
    created = await _create_schedule(
        client, data, name=f"Run {uuid.uuid4().hex[:6]}"
    )
    schedule_id = created.json()["id"]

    monkeypatch.setattr(
        execute_mail_execution, "delay", lambda *_args, **_kwargs: None
    )

    response = await client.post(
        f"/api/v1/admin/mail/schedules/{schedule_id}/run"
    )

    assert response.status_code == 202, response.text
    execution_id = response.json()["execution_id"]

    execution = await session.get(MailExecution, uuid.UUID(execution_id))
    assert execution is not None
    assert execution.trigger == MailTrigger.MANUAL

    listing = await client.get("/api/v1/admin/mail/executions")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["schedule_name"] == created.json()["name"]


async def test_schedule_delete_removes_it(
    client: AsyncClient, session: AsyncSession
) -> None:
    data = await _mail_fixture(client, session)
    created = await _create_schedule(
        client, data, name=f"Delete {uuid.uuid4().hex[:6]}"
    )
    schedule_id = created.json()["id"]

    assert (
        await client.delete(f"/api/v1/admin/mail/schedules/{schedule_id}")
    ).status_code == 204
    assert (
        await client.get(f"/api/v1/admin/mail/schedules/{schedule_id}")
    ).status_code == 404


async def test_user_cannot_access_mail_admin(
    client: AsyncClient, session: AsyncSession
) -> None:
    member = await make_user(
        session, email=f"member-{uuid.uuid4().hex[:8]}@example.com"
    )
    assert (await login(client, member.email)).status_code == 200

    assert (await client.get("/api/v1/admin/mail/settings")).status_code == 403
    assert (await client.get("/api/v1/admin/mail/schedules")).status_code == 403
