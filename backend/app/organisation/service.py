"""Organisation settings."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit
from app.core.exceptions import NotFoundError
from app.organisation.models import ORGANISATION_ID, Organisation
from app.organisation.schemas import OrganisationUpdate


def _snapshot(org: Organisation) -> dict[str, object]:
    return {
        "name": org.name,
        "description": org.description,
        "industry": org.industry,
        "locations": org.locations,
        "timezone": org.timezone,
    }


async def get_organisation(session: AsyncSession) -> Organisation:
    organisation = await session.get(Organisation, ORGANISATION_ID)
    if organisation is None:
        raise NotFoundError("Organisation has not been configured yet")
    return organisation


async def update_organisation(
    session: AsyncSession,
    *,
    payload: OrganisationUpdate,
    actor_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> Organisation:
    organisation = await get_organisation(session)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return organisation

    if "name" in changes and changes["name"] is not None:
        changes["name"] = str(changes["name"]).strip()

    before = _snapshot(organisation)
    for field, value in changes.items():
        setattr(organisation, field, value)
    await session.flush()

    await record_audit(
        session,
        actor_id=actor_id,
        action="organisation.updated",
        entity_type="organisation",
        entity_id=str(organisation.id),
        before=before,
        after=_snapshot(organisation),
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    return organisation
