import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.users.models import AccountStatus, UserRole


class DepartmentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    status: AccountStatus
    department_id: uuid.UUID
    department: DepartmentSummary | None = None
    must_change_password: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    department_id: uuid.UUID
    role: UserRole = UserRole.USER


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    department_id: uuid.UUID | None = None
    role: UserRole | None = None
    status: AccountStatus | None = None


class UserCreated(UserRead):
    temporary_password: str


class PasswordResetResponse(BaseModel):
    temporary_password: str
