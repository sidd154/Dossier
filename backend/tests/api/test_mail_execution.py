import uuid
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import func, select

from app.core.exceptions import UpstreamError
from app.mail.dispatch import dispatch_due_schedules
from app.mail.execution import execute_execution
from app.mail.executions_service import create_manual_execution
from app.mail.models import (
    MailDelivery,
    MailDeliveryStatus,
    MailExecution,
    MailExecutionStatus,
    MailFrequency,
    MailSchedule,
    MailTemplate,
)
from app.users.models import AccountStatus
from tests.conftest import (
    configure_mail_settings,
    make_department,
    make_organisation,
    make_source_snapshot,
    make_user,
)


async def _setup(session):
    await make_organisation(session)
    await configure_mail_settings(session)

    sales = await make_department(session, name="Sales")
    finance = await make_department(session, name="Finance")
    sales_user = await make_user(
        session, email="sales@example.com", department=sales, full_name="Sam Sales"
    )
    finance_user = await make_user(
        session, email="finance@example.com", department=finance, full_name="Fiona Finance"
    )
    await make_user(
        session,
        email="disabled@example.com",
        department=sales,
        status=AccountStatus.DISABLED,
    )

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

    template = MailTemplate(
        name=f"Brief {uuid.uuid4().hex[:6]}",
        subject_template="{{ department.name }} brief",
        system_prompt="Summarise the numbers for the team.",
        is_active=True,
    )
    session.add(template)
    await session.commit()

    return {
        "sales": sales,
        "finance": finance,
        "sales_user": sales_user,
        "finance_user": finance_user,
        "sales_source": sales_source,
        "finance_source": finance_source,
        "template": template,
    }


async def _make_schedule(
    session,
    *,
    template,
    department,
    sources,
    enabled: bool = True,
    next_run_at: datetime | None = None,
):
    schedule = MailSchedule(
        name=f"Schedule {uuid.uuid4().hex[:8]}",
        template_id=template.id,
        department_id=department.id,
        enabled=enabled,
        frequency=MailFrequency.DAILY,
        time_of_day=time(9, 0),
        timezone="UTC",
        row_limit=10,
        next_run_at=next_run_at or (datetime.now(UTC) + timedelta(days=1)),
    )
    schedule.sources = sources
    session.add(schedule)
    await session.commit()
    return schedule


async def test_each_department_only_ever_sees_its_own_sources(
    session, fake_llm, fake_smtp
) -> None:
    data = await _setup(session)

    # Both schedules select both sources. Only the department's grants decide what
    # is actually placed in the prompt.
    sales_schedule = await _make_schedule(
        session,
        template=data["template"],
        department=data["sales"],
        sources=[data["sales_source"], data["finance_source"]],
    )
    finance_schedule = await _make_schedule(
        session,
        template=data["template"],
        department=data["finance"],
        sources=[data["sales_source"], data["finance_source"]],
    )

    sales_execution = await create_manual_execution(
        session, schedule_id=sales_schedule.id
    )
    finance_execution = await create_manual_execution(
        session, schedule_id=finance_schedule.id
    )

    sales_result = await execute_execution(session, sales_execution.id)
    finance_result = await execute_execution(session, finance_execution.id)

    assert sales_result.status == MailExecutionStatus.SUCCEEDED
    assert finance_result.status == MailExecutionStatus.SUCCEEDED
    assert len(fake_smtp) == 2
    assert len(fake_llm.calls) == 2

    sales_prompt = next(prompt for prompt in fake_llm.prompts if "Sales Data" in prompt)
    finance_prompt = next(
        prompt for prompt in fake_llm.prompts if "Finance Data" in prompt
    )

    assert "Finance Data" not in sales_prompt
    assert "Secret Fund" not in sales_prompt
    assert "9999" not in sales_prompt
    assert "Sales Data" not in finance_prompt
    assert "Alpha" not in finance_prompt

    recipients = {str(message["To"]) for message in fake_smtp}
    assert recipients == {"sales@example.com", "finance@example.com"}
    for message in fake_smtp:
        body = message.get_content()
        assert body.startswith("Hello ")
        assert "Generated summary body." in body

    deliveries = (
        await session.execute(
            select(MailDelivery).where(
                MailDelivery.execution_id.in_(
                    [sales_execution.id, finance_execution.id]
                )
            )
        )
    ).scalars().all()
    assert {delivery.status for delivery in deliveries} == {MailDeliveryStatus.SENT}
    assert all(delivery.subject and delivery.body for delivery in deliveries)


async def test_generation_failure_sends_nothing(
    session, fake_llm, fake_smtp
) -> None:
    data = await _setup(session)
    schedule = await _make_schedule(
        session,
        template=data["template"],
        department=data["sales"],
        sources=[data["sales_source"]],
    )
    execution = await create_manual_execution(session, schedule_id=schedule.id)
    fake_llm.error = UpstreamError("model down")

    result = await execute_execution(session, execution.id)

    assert result.status == MailExecutionStatus.FAILED
    assert result.sent_count == 0
    assert result.failed_count == 1
    assert fake_smtp == []

    delivery = (
        await session.execute(
            select(MailDelivery).where(MailDelivery.execution_id == execution.id)
        )
    ).scalar_one()
    assert delivery.status == MailDeliveryStatus.FAILED
    assert "Generation failed" in (delivery.error or "")


async def test_department_without_grants_is_skipped_not_sent(
    session, fake_llm, fake_smtp
) -> None:
    data = await _setup(session)
    # Finance has no grant over the Sales source, so nothing may be used.
    schedule = await _make_schedule(
        session,
        template=data["template"],
        department=data["finance"],
        sources=[data["sales_source"]],
    )
    execution = await create_manual_execution(session, schedule_id=schedule.id)

    result = await execute_execution(session, execution.id)

    assert result.status == MailExecutionStatus.SKIPPED
    assert result.recipient_count == 1
    assert result.sent_count == 0
    assert result.skipped_count == 1
    assert fake_smtp == []
    assert fake_llm.calls == []

    skipped = (
        await session.execute(
            select(MailDelivery).where(MailDelivery.execution_id == execution.id)
        )
    ).scalar_one()
    assert skipped.status == MailDeliveryStatus.SKIPPED
    assert "No permitted sources" in (skipped.error or "")
    assert skipped.email == "finance@example.com"


async def test_only_active_department_members_receive(
    session, fake_llm, fake_smtp
) -> None:
    data = await _setup(session)
    await make_user(
        session,
        email="sales2@example.com",
        department=data["sales"],
        full_name="Sasha Sales",
    )
    schedule = await _make_schedule(
        session,
        template=data["template"],
        department=data["sales"],
        sources=[data["sales_source"]],
    )
    execution = await create_manual_execution(session, schedule_id=schedule.id)

    result = await execute_execution(session, execution.id)

    assert result.recipient_count == 2
    assert result.sent_count == 2
    recipients = {str(message["To"]) for message in fake_smtp}
    assert recipients == {"sales@example.com", "sales2@example.com"}
    assert "disabled@example.com" not in recipients


async def test_department_with_no_members_is_skipped(
    session, fake_llm, fake_smtp
) -> None:
    data = await _setup(session)
    empty = await make_department(session, name="Empty")
    source = await make_source_snapshot(
        session, name="Empty Data", rows=[{"A": 1}], department=empty
    )
    schedule = await _make_schedule(
        session,
        template=data["template"],
        department=empty,
        sources=[source],
    )
    execution = await create_manual_execution(session, schedule_id=schedule.id)

    result = await execute_execution(session, execution.id)

    assert result.status == MailExecutionStatus.SKIPPED
    assert result.recipient_count == 0
    assert result.error == "This department has no active members"
    assert fake_smtp == []


async def test_missing_smtp_fails_the_execution_before_generation(
    session, fake_llm, fake_smtp
) -> None:
    await make_organisation(session)
    sales = await make_department(session, name="Sales")
    await make_user(session, email="sales@example.com", department=sales)
    source = await make_source_snapshot(
        session, name="Sales Data", rows=[{"Deal": "Alpha"}], department=sales
    )
    template = MailTemplate(
        name="Brief", subject_template="Subject", system_prompt="Prompt", is_active=True
    )
    session.add(template)
    await session.commit()
    schedule = await _make_schedule(
        session, template=template, department=sales, sources=[source]
    )
    execution = await create_manual_execution(session, schedule_id=schedule.id)

    result = await execute_execution(session, execution.id)

    assert result.status == MailExecutionStatus.FAILED
    assert result.error == "SMTP settings are not configured"
    assert fake_llm.calls == []
    assert fake_smtp == []


async def test_dispatch_is_idempotent_for_the_same_slot(session) -> None:
    data = await _setup(session)
    schedule = await _make_schedule(
        session,
        template=data["template"],
        department=data["sales"],
        sources=[data["sales_source"]],
    )
    past = datetime.now(UTC) - timedelta(hours=1)
    schedule.next_run_at = past
    await session.commit()

    now = datetime.now(UTC)
    first = await dispatch_due_schedules(session, now=now)
    assert len(first) == 1

    schedule.next_run_at = past
    await session.commit()
    second = await dispatch_due_schedules(session, now=now)

    assert second == []
    total = await session.scalar(
        select(func.count())
        .select_from(MailExecution)
        .where(MailExecution.schedule_id == schedule.id)
    )
    assert total == 1

    await session.refresh(schedule)
    assert schedule.next_run_at is not None
    assert schedule.next_run_at > now
