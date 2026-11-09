import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("ip", mode="before")
    @classmethod
    def _stringify_ip(cls, value: object) -> object:
        # asyncpg returns ipaddress.IPv4Address/IPv6Address for INET columns.
        return None if value is None else str(value)

    id: int
    actor_user_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: str | None
    before: dict[str, object] | None
    after: dict[str, object] | None
    ip: str | None
    user_agent: str | None
    created_at: datetime
