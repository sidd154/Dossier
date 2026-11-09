import pytest
from cryptography.fernet import Fernet

from app.config import get_settings
from app.core.crypto import decrypt_credentials, encrypt_credentials
from app.core.exceptions import AppError


def test_roundtrip() -> None:
    key_id, ciphertext = encrypt_credentials(
        {"client_email": "svc@example.com", "private_key": "secret"}
    )
    assert key_id
    assert decrypt_credentials(key_id, ciphertext) == {
        "client_email": "svc@example.com",
        "private_key": "secret",
    }


def test_ciphertext_does_not_contain_the_plaintext() -> None:
    _, ciphertext = encrypt_credentials({"private_key": "super-secret-value"})
    assert b"super-secret-value" not in ciphertext


def test_unknown_key_id_is_rejected() -> None:
    with pytest.raises(AppError):
        decrypt_credentials("does-not-exist", b"whatever")


def test_tampered_ciphertext_is_rejected() -> None:
    key_id, ciphertext = encrypt_credentials({"value": "one"})
    tampered = ciphertext[:-4] + b"AAAA"
    with pytest.raises(AppError):
        decrypt_credentials(key_id, tampered)


def test_old_keys_remain_readable_during_rotation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    future_key = Fernet.generate_key().decode()

    monkeypatch.setattr(settings, "credential_encryption_keys", f"v1:{old_key},v2:{new_key}")
    monkeypatch.setattr(settings, "credential_encryption_active_key_id", "v2")
    key_id, ciphertext = encrypt_credentials({"value": "rotating"})
    assert key_id == "v2"

    # Activate a third key; values written under v2 must still decrypt.
    monkeypatch.setattr(
        settings,
        "credential_encryption_keys",
        f"v1:{old_key},v2:{new_key},v3:{future_key}",
    )
    monkeypatch.setattr(settings, "credential_encryption_active_key_id", "v3")

    assert decrypt_credentials(key_id, ciphertext) == {"value": "rotating"}
    assert encrypt_credentials({"value": "new"})[0] == "v3"
