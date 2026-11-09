"""Import every model so Alembic sees the full metadata."""

from app.audit.models import AuditLog
from app.auth.models import RefreshToken
from app.connectors.models import Connector, ConnectorCredential
from app.data_sources.models import DataSource, DataSourcePermission
from app.departments.models import Department
from app.mail.models import (
    MailDelivery,
    MailExecution,
    MailSchedule,
    MailSettings,
    MailTemplate,
)
from app.organisation.models import Organisation
from app.snapshots.models import Snapshot, SnapshotRecord
from app.sync.models import SyncJob
from app.users.models import AppUser

__all__ = [
    "AppUser",
    "AuditLog",
    "Connector",
    "ConnectorCredential",
    "DataSource",
    "DataSourcePermission",
    "Department",
    "MailDelivery",
    "MailExecution",
    "MailSchedule",
    "MailSettings",
    "MailTemplate",
    "Organisation",
    "RefreshToken",
    "Snapshot",
    "SnapshotRecord",
    "SyncJob",
]
