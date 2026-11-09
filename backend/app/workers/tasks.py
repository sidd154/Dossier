"""Celery tasks. Each task owns its own database session and event loop."""

import asyncio
import uuid

from sqlalchemy import select

from app.core.logging import get_logger
from app.data_sources.models import DataSource
from app.database.session import async_session_factory, engine
from app.mail.dispatch import dispatch_due_schedules
from app.mail.execution import execute_execution
from app.sync.models import SyncTrigger
from app.sync.service import run_sync
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="app.workers.tasks.sync_data_source")
def sync_data_source(data_source_id: str) -> str:
    return asyncio.run(_sync_one(data_source_id))


async def _sync_one(data_source_id: str) -> str:
    try:
        async with async_session_factory() as session:
            job = await run_sync(
                session,
                data_source_id=uuid.UUID(data_source_id),
                trigger=SyncTrigger.SCHEDULED,
            )
            return f"{job.status.value} ({job.record_count or 0} records)"
    finally:
        await engine.dispose()


@celery_app.task(name="app.workers.tasks.sync_all_sources")
def sync_all_sources() -> dict[str, str]:
    return asyncio.run(_sync_all())


async def _sync_all() -> dict[str, str]:
    results: dict[str, str] = {}
    try:
        async with async_session_factory() as session:
            ids = (
                await session.execute(
                    select(DataSource.id).where(DataSource.is_active.is_(True))
                )
            ).scalars().all()

        for data_source_id in ids:
            try:
                async with async_session_factory() as session:
                    job = await run_sync(
                        session,
                        data_source_id=data_source_id,
                        trigger=SyncTrigger.SCHEDULED,
                    )
                    results[str(data_source_id)] = job.status.value
            except Exception as exc:
                logger.warning(
                    "Scheduled sync failed", data_source_id=str(data_source_id), error=str(exc)
                )
                results[str(data_source_id)] = "ERROR"
    finally:
        await engine.dispose()
    return results


@celery_app.task(name="app.workers.tasks.dispatch_mail_schedules")
def dispatch_mail_schedules() -> int:
    return asyncio.run(_dispatch_mail())


async def _dispatch_mail() -> int:
    try:
        async with async_session_factory() as session:
            execution_ids = await dispatch_due_schedules(session)
        for execution_id in execution_ids:
            execute_mail_execution.delay(str(execution_id))
        return len(execution_ids)
    finally:
        await engine.dispose()


@celery_app.task(name="app.workers.tasks.execute_mail_execution")
def execute_mail_execution(execution_id: str) -> str:
    return asyncio.run(_execute_mail(execution_id))


async def _execute_mail(execution_id: str) -> str:
    try:
        async with async_session_factory() as session:
            execution = await execute_execution(session, uuid.UUID(execution_id))
            return execution.status.value
    finally:
        await engine.dispose()
