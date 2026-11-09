"""SMTP settings and test delivery."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit
from app.core.crypto import decrypt_credentials, encrypt_credentials
from app.core.exceptions import AppError, ConflictError
from app.database.mixins import utcnow
from app.mail.models import (
    MAIL_SETTINGS_ID,
    MailSettings,
    SmtpSecurity,
)
from app.mail.schemas import MailSettingsRead, MailSettingsUpdate, MailTestResult
from app.mail.sender import SmtpConfig, send_test_email
from app.organisation.service import get_organisation


async def get_mail_settings(session: AsyncSession) -> MailSettings | None:
    return await session.get(MailSettings, MAIL_SETTINGS_ID)


def to_read(row: MailSettings) -> MailSettingsRead:
    return MailSettingsRead(
        host=row.host,
        port=row.port,
        username=row.username,
        from_email=row.from_email,
        from_name=row.from_name,
        security=row.security,
        has_password=row.ciphertext is not None,
        last_tested_at=row.last_tested_at,
        last_test_error=row.last_test_error,
        updated_at=row.updated_at,
    )


def _audit_snapshot(row: MailSettings) -> dict[str, object]:
    return {
        "host": row.host,
        "port": row.port,
        "username": row.username,
        "from_email": row.from_email,
        "from_name": row.from_name,
        "security": row.security.value,
        "has_password": row.ciphertext is not None,
    }


def build_smtp_config(row: MailSettings) -> SmtpConfig:
    password: str | None = None
    if row.ciphertext is not None:
        if row.key_id is None:
            raise ConflictError(
                "Stored SMTP password is unreadable; set it again.",
                code="smtp_password_unreadable",
            )
        payload = decrypt_credentials(row.key_id, row.ciphertext)
        password = str(payload.get("password") or "")

    return SmtpConfig(
        host=row.host,
        port=row.port,
        username=row.username,
        password=password,
        from_email=row.from_email,
        from_name=row.from_name,
        security=row.security,
    )


async def update_mail_settings(
    session: AsyncSession,
    *,
    payload: MailSettingsUpdate,
    actor_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> MailSettings:
    row = await get_mail_settings(session)
    creating = row is None
    if row is None:
        row = MailSettings(
            id=MAIL_SETTINGS_ID,
            host="",
            port=587,
            from_email="",
            security=SmtpSecurity.STARTTLS,
        )
        session.add(row)
        before = None
    else:
        before = _audit_snapshot(row)

    changes = payload.model_dump(exclude_unset=True)
    password = changes.pop("password", None)
    clear_password = changes.pop("clear_password", False)

    for field, value in changes.items():
        setattr(row, field, value)

    if password:
        key_id, ciphertext = encrypt_credentials({"password": password})
        row.key_id = key_id
        row.ciphertext = ciphertext
    elif clear_password:
        row.key_id = None
        row.ciphertext = None

    row.host = row.host.strip()
    row.from_email = str(row.from_email).strip()
    if not row.host:
        raise ConflictError("An SMTP host is required", code="smtp_incomplete")
    if not row.from_email:
        raise ConflictError(
            "A sender email address is required", code="smtp_incomplete"
        )

    if creating:
        await session.flush()

    await record_audit(
        session,
        actor_id=actor_id,
        action="mail_settings.updated",
        entity_type="mail_settings",
        entity_id=str(MAIL_SETTINGS_ID),
        before=before,
        after=_audit_snapshot(row),
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    return row


async def test_mail_settings(
    session: AsyncSession, *, to_email: str
) -> MailTestResult:
    row = await get_mail_settings(session)
    if row is None:
        raise ConflictError("Configure SMTP settings first", code="smtp_missing")

    try:
        config = build_smtp_config(row)
        organisation = await get_organisation(session)
        await send_test_email(
            config, to_email=to_email, organisation_name=organisation.name
        )
    except AppError as exc:
        row.last_test_error = exc.detail[:2000]
        await session.commit()
        return MailTestResult(ok=False, error=exc.detail)
    except Exception as exc:
        row.last_test_error = f"{type(exc).__name__}: {exc}"[:2000]
        await session.commit()
        return MailTestResult(ok=False, error=row.last_test_error)

    row.last_tested_at = utcnow()
    row.last_test_error = None
    await session.commit()
    return MailTestResult(ok=True, last_tested_at=row.last_tested_at)
