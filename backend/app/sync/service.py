"""The highest-consequence path in the product: fetching and promoting a snapshot.

Rules enforced here:
  * the previous snapshot is never modified or deleted;
  * ``current_snapshot_id`` is updated in the same transaction that writes every row
    of the new snapshot, and only after all writes succeed;
  * a failed fetch produces a FAILED job and leaves the previous snapshot serving;
  * concurrent syncs of the same source are excluded by a Redis lock.
"""

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.connectors.base import ConnectorError
from app.connectors.models import Connector
from app.connectors.registry import get_connector
from app.core.crypto import decrypt_credentials
from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.locks import exclusive_lock
from app.data_sources.models import DataSource
from app.database.mixins import utcnow
from app.snapshots.models import Snapshot, SnapshotRecord, SnapshotStatus
from app.sync.models import SyncJob, SyncStatus, SyncTrigger


async def _load_source(session: AsyncSession, data_source_id: uuid.UUID) -> DataSource:
    result = await session.execute(
        select(DataSource)
        .options(selectinload(DataSource.connector).selectinload(Connector.credential))
        .where(DataSource.id == data_source_id)
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise NotFoundError("Data source not found")
    return source


def schema_hash(columns: list[str]) -> str:
    return hashlib.sha256(json.dumps(columns).encode("utf-8")).hexdigest()


def _external_id(row: dict[str, Any]) -> str | None:
    value = row.get("id")
    if isinstance(value, (str, int)):
        return str(value)[:255]
    return None


async def _mark_failed(session: AsyncSession, job: SyncJob, message: str) -> None:
    job.status = SyncStatus.FAILED
    job.error = message[:2000]
    job.finished_at = utcnow()
    await session.commit()


async def run_sync(
    session: AsyncSession,
    *,
    data_source_id: uuid.UUID,
    trigger: SyncTrigger = SyncTrigger.MANUAL,
    actor_id: uuid.UUID | None = None,
) -> SyncJob:
    source = await _load_source(session, data_source_id)
    connector_model = source.connector

    if not source.is_active:
        raise ConflictError("This data source is inactive", code="source_inactive")
    if not connector_model.is_active:
        raise ConflictError("The connector is inactive", code="connector_inactive")
    credential = connector_model.credential
    if credential is None:
        raise ConflictError(
            "This connector has no stored credentials", code="missing_credentials"
        )

    async with exclusive_lock(f"sync:{data_source_id}"):
        job = SyncJob(
            data_source_id=source.id,
            status=SyncStatus.RUNNING,
            trigger=trigger,
            actor_user_id=actor_id,
            started_at=utcnow(),
        )
        session.add(job)
        await session.commit()

        try:
            adapter = get_connector(
                connector_model.type,
                config=dict(connector_model.config),
                credentials=decrypt_credentials(credential.key_id, credential.ciphertext),
            )
            table = await adapter.fetch(dict(source.config))
        except ConnectorError as exc:
            await _mark_failed(session, job, str(exc))
            return job
        except AppError as exc:
            # e.g. credentials that can no longer be decrypted
            await _mark_failed(session, job, exc.detail)
            return job
        except Exception as exc:
            await _mark_failed(
                session, job, f"Unexpected sync failure ({type(exc).__name__})"
            )
            return job

        snapshot = Snapshot(
            data_source_id=source.id,
            status=(
                SnapshotStatus.PARTIAL if table.partial else SnapshotStatus.READY
            ),
            record_count=len(table.rows),
            schema_hash=schema_hash(table.columns),
            source_metadata={**table.metadata, "columns": table.columns},
        )
        session.add(snapshot)
        await session.flush()

        if table.rows:
            await session.execute(
                insert(SnapshotRecord),
                [
                    {
                        "snapshot_id": snapshot.id,
                        "row_index": index,
                        "external_id": _external_id(row),
                        "payload": row,
                    }
                    for index, row in enumerate(table.rows)
                ],
            )

        # Promotion happens only now, inside this transaction, after every write.
        source.current_snapshot_id = snapshot.id
        source.schema_hash = snapshot.schema_hash
        job.status = SyncStatus.PARTIAL if table.partial else SyncStatus.SUCCEEDED
        job.record_count = len(table.rows)
        job.snapshot_id = snapshot.id
        job.finished_at = utcnow()
        await session.commit()
        return job
