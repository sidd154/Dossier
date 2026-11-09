"""The single source of truth for what a user may retrieve.

``allowed_source_ids`` is resolved from the user's department before any retrieval
happens. There is no representation of "all sources": an empty set means no data, not
unrestricted access. Phase 3 retrieval and Phase 4 mail must both take their filters
from here.
"""

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import UserRole

if TYPE_CHECKING:
    from app.users.models import AppUser


@dataclass(frozen=True, slots=True)
class PermissionContext:
    user_id: uuid.UUID
    role: UserRole
    department_id: uuid.UUID
    allowed_source_ids: frozenset[uuid.UUID]

    def can_access_source(self, source_id: uuid.UUID) -> bool:
        return source_id in self.allowed_source_ids


async def resolve_allowed_source_ids(
    session: AsyncSession, department_id: uuid.UUID
) -> frozenset[uuid.UUID]:
    """Grants for one department, restricted to sources that are currently usable."""
    from app.data_sources.models import DataSource, DataSourcePermission

    rows = await session.execute(
        select(DataSourcePermission.data_source_id)
        .join(DataSource, DataSource.id == DataSourcePermission.data_source_id)
        .where(
            DataSourcePermission.department_id == department_id,
            DataSource.is_active.is_(True),
        )
    )
    return frozenset(rows.scalars().all())


def build_permission_context(
    user: "AppUser", allowed_source_ids: frozenset[uuid.UUID] = frozenset()
) -> PermissionContext:
    """Pure constructor. The default is deliberately empty (fail-closed)."""
    return PermissionContext(
        user_id=user.id,
        role=user.role,
        department_id=user.department_id,
        allowed_source_ids=allowed_source_ids,
    )


async def resolve_permission_context(
    session: AsyncSession, user: "AppUser"
) -> PermissionContext:
    allowed = await resolve_allowed_source_ids(session, user.department_id)
    return build_permission_context(user, allowed)
