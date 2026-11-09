import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.snapshots.models import SnapshotStatus
from app.sync.models import SyncStatus, SyncTrigger


class DataSourceCreate(BaseModel):
    connector_id: uuid.UUID
    external_id: str = Field(min_length=1, max_length=255)
    name: str | None = Field(default=None, max_length=200)
    is_active: bool = True


class DataSourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None
    config: dict[str, Any] | None = None


class SnapshotSummary(BaseModel):
    id: uuid.UUID
    captured_at: datetime
    status: SnapshotStatus
    record_count: int


class DataSourceRead(BaseModel):
    id: uuid.UUID
    connector_id: uuid.UUID
    connector_name: str
    connector_type: str
    external_id: str
    name: str
    kind: str
    config: dict[str, Any]
    is_active: bool
    schema_hash: str | None
    current_snapshot: SnapshotSummary | None
    created_at: datetime
    updated_at: datetime


class SyncJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    data_source_id: uuid.UUID
    status: SyncStatus
    trigger: SyncTrigger
    actor_user_id: uuid.UUID | None
    started_at: datetime
    finished_at: datetime | None
    error: str | None
    record_count: int | None
    snapshot_id: uuid.UUID | None


class SnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    data_source_id: uuid.UUID
    captured_at: datetime
    status: SnapshotStatus
    record_count: int
    schema_hash: str | None
    source_metadata: dict[str, Any]


class DepartmentSourceEntry(BaseModel):
    data_source_id: uuid.UUID
    name: str
    kind: str
    connector_name: str
    granted: bool


class DepartmentSourcesRead(BaseModel):
    department_id: uuid.UUID
    department_name: str
    entries: list[DepartmentSourceEntry]


class DepartmentSourcesUpdate(BaseModel):
    data_source_ids: list[uuid.UUID]
