"""Connector configuration, credential storage, and validation."""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit.service import record_audit
from app.connectors.base import BaseConnector, ConnectorAsset, ConnectorError
from app.connectors.models import Connector, ConnectorCredential, ConnectorType
from app.connectors.registry import get_connector
from app.connectors.schemas import (
    ConnectorCreate,
    ConnectorRead,
    ConnectorUpdate,
    ConnectorValidationResult,
)
from app.core.crypto import decrypt_credentials, encrypt_credentials
from app.core.exceptions import ConflictError, NotFoundError, UpstreamError
from app.database.mixins import utcnow


def to_read(connector: Connector) -> ConnectorRead:
    return ConnectorRead(
        id=connector.id,
        name=connector.name,
        type=connector.type,
        is_active=connector.is_active,
        config=dict(connector.config),
        has_credentials=connector.credential is not None,
        last_validated_at=connector.last_validated_at,
        last_validation_error=connector.last_validation_error,
        created_at=connector.created_at,
        updated_at=connector.updated_at,
    )


def _audit_snapshot(connector: Connector) -> dict[str, object]:
    return {
        "name": connector.name,
        "type": connector.type.value,
        "is_active": connector.is_active,
        "config": dict(connector.config),
        "has_credentials": connector.credential is not None,
    }


async def list_connectors(
    session: AsyncSession,
    *,
    q: str | None,
    connector_type: ConnectorType | None,
    is_active: bool | None,
    page: int,
    page_size: int,
) -> tuple[list[Connector], int]:
    conditions: list[Any] = []
    if q:
        conditions.append(Connector.name.ilike(f"%{q.strip()}%"))
    if connector_type is not None:
        conditions.append(Connector.type == connector_type)
    if is_active is not None:
        conditions.append(Connector.is_active.is_(is_active))

    count_stmt = select(func.count()).select_from(Connector)
    list_stmt = select(Connector).options(selectinload(Connector.credential))
    if conditions:
        count_stmt = count_stmt.where(*conditions)
        list_stmt = list_stmt.where(*conditions)

    total = await session.scalar(count_stmt) or 0
    items = (
        await session.execute(
            list_stmt.order_by(Connector.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return list(items), total


async def get_connector_model(session: AsyncSession, connector_id: uuid.UUID) -> Connector:
    result = await session.execute(
        select(Connector)
        .options(selectinload(Connector.credential))
        .where(Connector.id == connector_id)
    )
    connector = result.scalar_one_or_none()
    if connector is None:
        raise NotFoundError("Connector not found")
    return connector


async def create_connector(
    session: AsyncSession,
    *,
    payload: ConnectorCreate,
    actor_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> Connector:
    name = payload.name.strip()
    if await session.scalar(select(Connector.id).where(Connector.name == name)):
        raise ConflictError("A connector with this name already exists", code="name_in_use")

    connector = Connector(
        name=name,
        type=payload.type,
        config=dict(payload.config),
        is_active=payload.is_active,
    )
    session.add(connector)
    await session.flush()

    if payload.credentials:
        key_id, ciphertext = encrypt_credentials(dict(payload.credentials))
        connector.credential = ConnectorCredential(
            connector_id=connector.id, key_id=key_id, ciphertext=ciphertext
        )
        await session.flush()

    await record_audit(
        session,
        actor_id=actor_id,
        action="connector.created",
        entity_type="connector",
        entity_id=str(connector.id),
        after=_audit_snapshot(connector),
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    return await get_connector_model(session, connector.id)


async def update_connector(
    session: AsyncSession,
    *,
    connector_id: uuid.UUID,
    payload: ConnectorUpdate,
    actor_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> Connector:
    connector = await get_connector_model(session, connector_id)
    changes = payload.model_dump(exclude_unset=True)
    credentials = changes.pop("credentials", None)

    if "name" in changes and changes["name"] is not None:
        name = str(changes["name"]).strip()
        clash = await session.scalar(
            select(Connector.id).where(
                Connector.name == name, Connector.id != connector.id
            )
        )
        if clash is not None:
            raise ConflictError(
                "A connector with this name already exists", code="name_in_use"
            )
        changes["name"] = name

    before = _audit_snapshot(connector)
    for field, value in changes.items():
        setattr(connector, field, value)

    if credentials:
        key_id, ciphertext = encrypt_credentials(dict(credentials))
        if connector.credential is None:
            connector.credential = ConnectorCredential(
                connector_id=connector.id, key_id=key_id, ciphertext=ciphertext
            )
        else:
            connector.credential.key_id = key_id
            connector.credential.ciphertext = ciphertext
            connector.credential.rotated_at = utcnow()
        # New credentials invalidate the previous validation result.
        connector.last_validation_error = None

    await session.flush()
    await record_audit(
        session,
        actor_id=actor_id,
        action="connector.updated",
        entity_type="connector",
        entity_id=str(connector.id),
        before=before,
        after=_audit_snapshot(connector),
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    return await get_connector_model(session, connector.id)


async def delete_connector(
    session: AsyncSession,
    *,
    connector_id: uuid.UUID,
    actor_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> None:
    connector = await get_connector_model(session, connector_id)
    before = _audit_snapshot(connector)
    await session.delete(connector)
    await record_audit(
        session,
        actor_id=actor_id,
        action="connector.deleted",
        entity_type="connector",
        entity_id=str(connector_id),
        before=before,
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()


def build_adapter(connector: Connector) -> BaseConnector:
    credential = connector.credential
    if credential is None:
        raise ConflictError(
            "This connector has no stored credentials", code="missing_credentials"
        )
    credentials = decrypt_credentials(credential.key_id, credential.ciphertext)
    return get_connector(
        connector.type, config=dict(connector.config), credentials=credentials
    )


async def validate_connector(
    session: AsyncSession, *, connector_id: uuid.UUID
) -> ConnectorValidationResult:
    connector = await get_connector_model(session, connector_id)
    try:
        adapter = build_adapter(connector)
        await adapter.validate()
    except ConnectorError as exc:
        connector.last_validation_error = str(exc)[:2000]
        await session.commit()
        return ConnectorValidationResult(ok=False, error=str(exc))
    except ConflictError:
        raise
    except Exception as exc:
        connector.last_validation_error = f"{type(exc).__name__}: {exc}"[:2000]
        await session.commit()
        return ConnectorValidationResult(ok=False, error=connector.last_validation_error)

    connector.last_validated_at = utcnow()
    connector.last_validation_error = None
    await session.commit()
    return ConnectorValidationResult(ok=True, last_validated_at=connector.last_validated_at)


async def list_assets(session: AsyncSession, *, connector_id: uuid.UUID) -> list[ConnectorAsset]:
    connector = await get_connector_model(session, connector_id)
    try:
        adapter = build_adapter(connector)
        return await adapter.list_assets()
    except ConnectorError as exc:
        raise UpstreamError(str(exc)) from exc
