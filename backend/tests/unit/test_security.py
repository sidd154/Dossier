import uuid
from datetime import timedelta

import jwt
import pytest

from app.config import get_settings
from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    generate_temporary_password,
    hash_password,
    hash_refresh_token,
    validate_password_strength,
    verify_and_rehash,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("Correct-Horse-Battery-Staple")
    assert hashed != "Correct-Horse-Battery-Staple"
    assert verify_password("Correct-Horse-Battery-Staple", hashed)
    assert not verify_password("wrong-password", hashed)


def test_verify_and_rehash_reports_outdated_hashes() -> None:
    hashed = hash_password("Correct-Horse-Battery-Staple")
    valid, replacement = verify_and_rehash("Correct-Horse-Battery-Staple", hashed)
    assert valid is True
    assert replacement is None


def test_access_token_roundtrip() -> None:
    user_id = uuid.uuid4()
    department_id = uuid.uuid4()
    token, expires_at = create_access_token(
        subject=user_id, role="USER", department_id=department_id
    )
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "USER"
    assert payload["dep"] == str(department_id)
    assert payload["typ"] == "access"
    assert expires_at is not None


def test_expired_token_is_rejected() -> None:
    token, _ = create_access_token(
        subject=uuid.uuid4(),
        role="USER",
        department_id=uuid.uuid4(),
        expires_delta=timedelta(seconds=-5),
    )
    with pytest.raises(AuthenticationError):
        decode_access_token(token)


def test_token_with_wrong_type_is_rejected() -> None:
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "role": "USER",
            "dep": str(uuid.uuid4()),
            "jti": str(uuid.uuid4()),
            "typ": "refresh",
            "iat": 0,
            "exp": 9_999_999_999,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(AuthenticationError):
        decode_access_token(token)


def test_token_signed_with_another_key_is_rejected() -> None:
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "role": "USER",
            "dep": str(uuid.uuid4()),
            "jti": str(uuid.uuid4()),
            "typ": "access",
            "iat": 0,
            "exp": 9_999_999_999,
        },
        "x" * 32,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(AuthenticationError):
        decode_access_token(token)


def test_refresh_tokens_are_random_and_hashed() -> None:
    first_raw, first_hash = generate_refresh_token()
    second_raw, _second_hash = generate_refresh_token()
    assert first_raw != second_raw
    assert first_hash == hash_refresh_token(first_raw)
    assert first_hash != first_raw
    assert len(first_hash) == 64


def test_temporary_password_shape() -> None:
    password = generate_temporary_password()
    assert len(password) == 16
    assert password != generate_temporary_password()


@pytest.mark.parametrize("length", [0, 11])
def test_short_passwords_are_rejected(length: int) -> None:
    with pytest.raises(ValueError):
        validate_password_strength("a" * length)


def test_long_passwords_are_rejected() -> None:
    with pytest.raises(ValueError):
        validate_password_strength("a" * 129)


def test_acceptable_password_passes() -> None:
    assert validate_password_strength("a" * 12) == "a" * 12
