from fastapi import APIRouter

from app.audit.router import router as audit_router
from app.auth.router import router as auth_router
from app.config import get_settings
from app.connectors.router import router as connectors_router
from app.data_sources.router import router as data_sources_router
from app.departments.router import router as departments_router
from app.mail.router import router as mail_router
from app.organisation.router import router as organisation_router
from app.sync.router import router as sync_jobs_router
from app.users.router import router as users_router

_settings = get_settings()

api_router = APIRouter(prefix=_settings.api_v1_prefix)
api_router.include_router(auth_router)

admin_router = APIRouter(prefix="/admin")
admin_router.include_router(organisation_router)
admin_router.include_router(departments_router)
admin_router.include_router(users_router)
admin_router.include_router(connectors_router)
admin_router.include_router(data_sources_router)
admin_router.include_router(sync_jobs_router)
admin_router.include_router(mail_router)
admin_router.include_router(audit_router)
api_router.include_router(admin_router)
