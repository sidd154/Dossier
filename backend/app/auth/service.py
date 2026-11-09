"""Authentication flows: login, refresh rotation, logout, password change."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit.service import record_audit
from app.auth.models import RefreshToken
from app.config import get_settings
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_and_rehash,
    verify_password,
)
from app.users.models import AccountStatus, AppUser

# A real hash to verify against when the email is unknown, so a failed login takes the
# same time whether or not the account exists.
_DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password")


@dataclass(frozen=True, slots=True)
class AuthResult:
    user: AppUser
    access_token: str
    refresh_token: str
    access_expires_in: int


def _issue(user: AppUser) -> tuple[str, int]:
    settings = get_settings()
    token, _ = create_access_token(
        subject=user.id,
        role=user.role.value,
        department_id=user.department_id,
    )
    return token, settings.access_token_ttl_minutes * 60


def _new_refresh_record(
    *,
    user_id: uuid.UUID,
    family_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> tuple[RefreshToken, str]:
    settings = get_settings()
    raw, hashed = generate_refresh_token()
    record = RefreshToken(
        user_id=user_id,
        token_hash=hashed,
        family_id=family_id,
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days),
        ip=ip,
        user_agent=user_agent,
    )
    return record, raw


async def _load_user_by_email(session: AsyncSession, email: str) -> AppUser | None:
    result = await session.execute(
        select(AppUser)
        .options(selectinload(AppUser.department))
        .where(AppUser.email == email.strip().lower())
    )
    return result.scalar_one_or_none()


async def _load_active_user(session: AsyncSession, user_id: uuid.UUID) -> AppUser | None:
    result = await session.execute(
        select(AppUser)
        .options(selectinload(AppUser.department))
        .where(AppUser.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None or user.status != AccountStatus.ACTIVE:
        return None
    return user


async def authenticate(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    ip: str | None,
    user_agent: str | None,
) -> AuthResult:
    user = await _load_user_by_email(session, email)

    if user is None:
        verify_password(password, _DUMMY_HASH)
        raise AuthenticationError("Invalid email or password", code="invalid_credentials")

    valid, upgraded_hash = verify_and_rehash(password, user.hashed_password)
    if not valid:
        raise AuthenticationError("Invalid email or password", code="invalid_credentials")

    if user.status != AccountStatus.ACTIVE:
        # Same generic message: account state is not disclosed to an unauthenticated caller.
        raise AuthenticationError("Invalid email or password", code="invalid_credentials")

    if upgraded_hash is not None:
        user.hashed_password = upgraded_hash

    user.last_login_at = datetime.now(UTC)

    record, raw_refresh = _new_refresh_record(
        user_id=user.id,
        family_id=uuid.uuid4(),
        ip=ip,
        user_agent=user_agent,
    )
    session.add(record)
    await session.commit()

    access_token, expires_in = _issue(user)
    return AuthResult(
        user=user,
        access_token=access_token,
        refresh_token=raw_refresh,
        access_expires_in=expires_in,
    )


async def rotate_refresh_token(
    session: AsyncSession,
    *,
    raw_token: str | None,
    ip: str | None,
    user_agent: str | None,
) -> AuthResult:
    if not raw_token:
        raise AuthenticationError("Not authenticated")

    token_hash = hash_refresh_token(raw_token)
    result = await session.execute(
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .with_for_update()
    )
    record = result.scalar_one_or_none()
    now = datetime.now(UTC)

    if record is None:
        raise AuthenticationError("Invalid session")

    if record.revoked_at is not None:
        # Reuse of a rotated token means the value leaked: invalidate the whole chain.
        await _revoke_family(session, record.family_id, now)
        await session.commit()
        raise AuthenticationError("Session has been revoked. Sign in again.")

    if record.expires_at <= now:
        record.revoked_at = now
        await session.commit()
        raise AuthenticationError("Session expired. Sign in again.")

    user = await _load_active_user(session, record.user_id)
    if user is None:
        await _revoke_family(session, record.family_id, now)
        await session.commit()
        raise AuthenticationError("Session is no longer valid. Sign in again.")

    replacement, raw_refresh = _new_refresh_record(
        user_id=user.id,
        family_id=record.family_id,
        ip=ip,
        user_agent=user_agent,
    )
    session.add(replacement)
    await session.flush()
    record.revoked_at = now
    record.replaced_by_id = replacement.id
    await session.commit()

    access_token, expires_in = _issue(user)
    return AuthResult(
        user=user,
        access_token=access_token,
        refresh_token=raw_refresh,
        access_expires_in=expires_in,
    )


async def revoke_session(session: AsyncSession, *, raw_token: str | None) -> None:
    if not raw_token:
        return
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
    )
    record = result.scalar_one_or_none()
    if record is None:
        return
    await _revoke_family(session, record.family_id, datetime.now(UTC))
    await session.commit()


async def change_password(
    session: AsyncSession,
    *,
    user: AppUser,
    current_password: str,
    new_password: str,
    ip: str | None,
    user_agent: str | None,
) -> AuthResult:
    valid, _ = verify_and_rehash(current_password, user.hashed_password)
    if not valid:
        raise AuthenticationError(
            "Current password is incorrect", code="invalid_credentials"
        )
    if current_password == new_password:
        raise ConflictError("New password must differ from the current password")

    user.hashed_password = hash_password(new_password)
    user.must_change_password = False

    now = datetime.now(UTC)
    await _revoke_all_user_tokens(session, user.id, now)

    # Mint a fresh family so the browser that changed the password stays signed in.
    record, raw_refresh = _new_refresh_record(
        user_id=user.id,
        family_id=uuid.uuid4(),
        ip=ip,
        user_agent=user_agent,
    )
    session.add(record)
    await record_audit(
        session,
        actor_id=user.id,
        action="auth.password_changed",
        entity_type="user",
        entity_id=str(user.id),
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()

    access_token, expires_in = _issue(user)
    return AuthResult(
        user=user,
        access_token=access_token,
        refresh_token=raw_refresh,
        access_expires_in=expires_in,
    )


async def _revoke_family(
    session: AsyncSession, family_id: uuid.UUID, now: datetime
) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )


async def revoke_all_user_tokens(session: AsyncSession, user_id: uuid.UUID) -> None:
    await _revoke_all_user_tokens(session, user_id, datetime.now(UTC))


async def _revoke_all_user_tokens(
    session: AsyncSession, user_id: uuid.UUID, now: datetime
) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
