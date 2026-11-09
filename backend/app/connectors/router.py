import uuid

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import AdminUser, DbSession, Meta, require_admin
from app.api.schemas import Page
from app.connectors.models import ConnectorType
from app.connectors.schemas import (
    ConnectorAssetRead,
    ConnectorCreate,
    ConnectorRead,
    ConnectorUpdate,
    ConnectorValidationResult,
)
from app.connectors.service import (
    create_connector,
    delete_connector,
    get_connector_model,
    list_assets,
    list_connectors,
    to_read,
    update_connector,
    validate_connector,
)

router = APIRouter(
    prefix="/connectors",
    tags=["admin:connectors"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=Page[ConnectorRead])
async def list_connectors_endpoint(
    session: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    connector_type: ConnectorType | None = Query(default=None, alias="type"),
    is_active: bool | None = None,
) -> Page[ConnectorRead]:
    items, total = await list_connectors(
        session,
        q=q,
        connector_type=connector_type,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )
    return Page[ConnectorRead](
        items=[to_read(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=ConnectorRead, status_code=201)
async def create_connector_endpoint(
    payload: ConnectorCreate,
    session: DbSession,
    admin: AdminUser,
    meta: Meta,
) -> ConnectorRead:
    connector = await create_connector(
        session,
        payload=payload,
        actor_id=admin.id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    return to_read(connector)


@router.get("/{connector_id}", response_model=ConnectorRead)
async def get_connector_endpoint(
    connector_id: uuid.UUID, session: DbSession
) -> ConnectorRead:
    return to_read(await get_connector_model(session, connector_id))


@router.patch("/{connector_id}", response_model=ConnectorRead)
async def update_connector_endpoint(
    connector_id: uuid.UUID,
    payload: ConnectorUpdate,
    session: DbSession,
    admin: AdminUser,
    meta: Meta,
) -> ConnectorRead:
    connector = await update_connector(
        session,
        connector_id=connector_id,
        payload=payload,
        actor_id=admin.id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    return to_read(connector)


@router.delete("/{connector_id}", status_code=204)
async def delete_connector_endpoint(
    connector_id: uuid.UUID,
    session: DbSession,
    admin: AdminUser,
    meta: Meta,
) -> Response:
    await delete_connector(
        session,
        connector_id=connector_id,
        actor_id=admin.id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    return Response(status_code=204)


@router.post("/{connector_id}/validate", response_model=ConnectorValidationResult)
async def validate_connector_endpoint(
    connector_id: uuid.UUID, session: DbSession
) -> ConnectorValidationResult:
    return await validate_connector(session, connector_id=connector_id)


@router.get("/{connector_id}/assets", response_model=list[ConnectorAssetRead])
async def list_assets_endpoint(
    connector_id: uuid.UUID, session: DbSession
) -> list[ConnectorAssetRead]:
    assets = await list_assets(session, connector_id=connector_id)
    return [
        ConnectorAssetRead(
            external_id=asset.external_id,
            name=asset.name,
            kind=asset.kind,
            config=dict(asset.config),
        )
        for asset in assets
    ]
