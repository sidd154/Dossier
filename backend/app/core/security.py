"""Password hashing, JWT issuance, and refresh-token helpers."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.config import get_settings
from app.core.exceptions import AuthenticationError

# Argon2id. pwdlib's recommended configuration tracks current OWASP guidance.
_password_hash = PasswordHash.recommended()

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _password_hash.verify(password, hashed)


def verify_and_rehash(password: str, hashed: str) -> tuple[bool, str | None]:
    """Verify and return a replacement hash if the parameters are outdated."""
    return _password_hash.verify_and_update(password, hashed)


def create_access_token(
    *,
    subject: uuid.UUID,
    role: str,
    department_id: uuid.UUID,
    expires_delta: timedelta | None = None,
) -> tuple[str, datetime]:
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + (
        expires_delta or timedelta(minutes=settings.access_token_ttl_minutes)
    )
    payload = {
        "sub": str(subject),
        "role": role,
        "dep": str(department_id),
        "jti": str(uuid.uuid4()),
        "typ": "access",
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_access_token(token: str) -> dict[str, object]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            # Pinning the algorithm list prevents "alg: none" and algorithm-confusion attacks.
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "sub", "typ", "jti"]},
        )
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid or expired token") from exc

    if payload.get("typ") != "access":
        raise AuthenticationError("Invalid token type")
    return payload


def generate_refresh_token() -> tuple[str, str]:
    """Return ``(raw_token, sha256_hex)``. Only the hash is ever persisted."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_temporary_password(length: int = 16) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def validate_password_strength(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_LENGTH} characters")
    return password
