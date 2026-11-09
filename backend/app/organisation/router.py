from fastapi import APIRouter, Depends

from app.api.deps import AdminUser, DbSession, Meta, require_admin
from app.organisation.schemas import OrganisationRead, OrganisationUpdate
from app.organisation.service import get_organisation, update_organisation

router = APIRouter(
    prefix="/organisation",
    tags=["admin:organisation"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=OrganisationRead)
async def get_organisation_endpoint(session: DbSession) -> OrganisationRead:
    return OrganisationRead.model_validate(await get_organisation(session))


@router.patch("", response_model=OrganisationRead)
async def update_organisation_endpoint(
    payload: OrganisationUpdate,
    session: DbSession,
    admin: AdminUser,
    meta: Meta,
) -> OrganisationRead:
    organisation = await update_organisation(
        session,
        payload=payload,
        actor_id=admin.id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    return OrganisationRead.model_validate(organisation)
