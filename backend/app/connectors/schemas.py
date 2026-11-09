import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.connectors.models import ConnectorType


class ConnectorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: ConnectorType
    config: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, str] = Field(default_factory=dict)
    is_active: bool = True


class ConnectorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    config: dict[str, Any] | None = None
    credentials: dict[str, str] | None = None
    is_active: bool | None = None


class ConnectorRead(BaseModel):
    id: uuid.UUID
    name: str
    type: ConnectorType
    is_active: bool
    config: dict[str, Any]
    has_credentials: bool
    last_validated_at: datetime | None
    last_validation_error: str | None
    created_at: datetime
    updated_at: datetime


class ConnectorAssetRead(BaseModel):
    external_id: str
    name: str
    kind: str
    config: dict[str, Any]


class ConnectorValidationResult(BaseModel):
    ok: bool
    error: str | None = None
    last_validated_at: datetime | None = None
