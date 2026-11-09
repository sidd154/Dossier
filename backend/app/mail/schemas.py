import uuid
from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.mail.models import (
    MailDeliveryStatus,
    MailExecutionStatus,
    MailFrequency,
    MailTrigger,
    SmtpSecurity,
)

# ------------------------------------------------------------------ settings


class MailSettingsRead(BaseModel):
    host: str
    port: int
    username: str | None
    from_email: str
    from_name: str | None
    security: SmtpSecurity
    has_password: bool
    last_tested_at: datetime | None
    last_test_error: str | None
    updated_at: datetime


class MailSettingsUpdate(BaseModel):
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = Field(default=None, max_length=255)
    from_email: EmailStr | None = None
    from_name: str | None = Field(default=None, max_length=200)
    security: SmtpSecurity | None = None
    password: str | None = Field(default=None, max_length=500)
    clear_password: bool = False


class MailTestSendRequest(BaseModel):
    to: EmailStr


class MailTestResult(BaseModel):
    ok: bool
    error: str | None = None
    last_tested_at: datetime | None = None


# ------------------------------------------------------------------ templates


class MailTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    subject_template: str = Field(min_length=1, max_length=500)
    system_prompt: str = Field(min_length=1, max_length=8000)
    is_active: bool = True


class MailTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    subject_template: str | None = Field(default=None, min_length=1, max_length=500)
    system_prompt: str | None = Field(default=None, min_length=1, max_length=8000)
    is_active: bool | None = None


class MailTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    subject_template: str
    system_prompt: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MailPreviewRequest(BaseModel):
    department_id: uuid.UUID
    source_ids: list[uuid.UUID] = Field(min_length=1)


class MailPreviewResponse(BaseModel):
    ok: bool = True
    error: str | None = None
    subject: str
    body: str
    sources_used: list[str]
    sources_excluded: list[str]


class MailTemplateTestRequest(BaseModel):
    to: EmailStr
    department_id: uuid.UUID
    source_ids: list[uuid.UUID] = Field(min_length=1)


# ------------------------------------------------------------------ schedules


class MailScheduleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    template_id: uuid.UUID
    department_id: uuid.UUID
    enabled: bool = True
    frequency: MailFrequency
    time_of_day: time
    weekday: int | None = Field(default=None, ge=0, le=6)
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    timezone: str = Field(min_length=1, max_length=64)
    row_limit: int = Field(default=50, ge=1, le=500)
    source_ids: list[uuid.UUID] = Field(min_length=1)


class MailScheduleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    template_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    enabled: bool | None = None
    frequency: MailFrequency | None = None
    time_of_day: time | None = None
    weekday: int | None = Field(default=None, ge=0, le=6)
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    row_limit: int | None = Field(default=None, ge=1, le=500)
    source_ids: list[uuid.UUID] | None = None


class MailScheduleRead(BaseModel):
    id: uuid.UUID
    name: str
    template_id: uuid.UUID
    template_name: str
    department_id: uuid.UUID
    department_name: str
    enabled: bool
    frequency: MailFrequency
    time_of_day: time
    weekday: int | None
    day_of_month: int | None
    timezone: str
    row_limit: int
    next_run_at: datetime | None
    last_run_at: datetime | None
    source_ids: list[uuid.UUID]
    source_names: list[str]
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------ executions


class MailExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    schedule_id: uuid.UUID
    trigger: MailTrigger
    scheduled_for: datetime
    status: MailExecutionStatus
    started_at: datetime
    finished_at: datetime | None
    recipient_count: int
    sent_count: int
    failed_count: int
    skipped_count: int
    error: str | None


class MailDeliveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    status: MailDeliveryStatus
    error: str | None
    message_id: str | None
    subject: str | None
    body: str | None
    department_id: uuid.UUID | None
    recipient_user_id: uuid.UUID | None
    sent_at: datetime | None


class MailExecutionSummary(MailExecutionRead):
    schedule_name: str
    department_name: str


class MailExecutionDetail(MailExecutionRead):
    schedule_name: str
    department_name: str
    deliveries: list[MailDeliveryRead]


class MailRunResponse(BaseModel):
    execution_id: uuid.UUID
    status: MailExecutionStatus

