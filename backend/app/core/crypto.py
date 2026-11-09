"""Encryption for connector credentials at rest.

Ciphertext never leaves the backend: no API returns stored secrets, and the admin UI
can only replace them. Each value records the key id that produced it, so keys can be
rotated without re-encrypting everything at once.
"""

import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings
from app.core.exceptions import AppError


class CredentialError(AppError):
    status_code = 500
    code = "credential_error"


def encrypt_credentials(payload: dict[str, Any]) -> tuple[str, bytes]:
    """Return ``(key_id, ciphertext)``."""
    settings = get_settings()
    key_id = settings.credential_encryption_active_key_id
    key = settings.credential_key_map[key_id]
    token = Fernet(key).encrypt(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    return key_id, token


def decrypt_credentials(key_id: str, ciphertext: bytes) -> dict[str, Any]:
    settings = get_settings()
    key = settings.credential_key_map.get(key_id)
    if key is None:
        raise CredentialError(
            "Stored credentials were encrypted with an unknown key. "
            "Restore the key or replace the credentials."
        )
    try:
        plaintext = Fernet(key).decrypt(ciphertext)
    except InvalidToken as exc:
        raise CredentialError(
            "Stored credentials could not be decrypted. Replace them."
        ) from exc
    payload = json.loads(plaintext.decode("utf-8"))
    if not isinstance(payload, dict):
        raise CredentialError("Stored credentials are not a JSON object")
    return payload
