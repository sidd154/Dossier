"""Application configuration loaded from the environment."""

from functools import lru_cache
from typing import Literal

from cryptography.fernet import Fernet
from pydantic import EmailStr, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Dossier"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    database_url: str = Field(
        default="postgresql+asyncpg://dossier:dossier@localhost:5433/dossier"
    )
    test_database_url: str | None = None
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7
    cookie_secure: bool = False
    cookie_domain: str | None = None

    rate_limit_login_attempts: int = 5
    rate_limit_login_window_seconds: int = 60

    # Comma-separated "key_id:fernet_key" pairs. The active id identifies which key
    # encrypts new values; older keys stay readable during a rotation window.
    credential_encryption_keys: str = ""
    credential_encryption_active_key_id: str = "v1"

    daily_sync_hour_utc: int = 2
    sync_lock_ttl_seconds: int = 1800

    cors_origins: str = ""

    llm_provider: Literal["ollama", "openai", "anthropic"] = "ollama"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_chat_model: str = "deepseek-v4.1-flash:cloud"
    llm_timeout_seconds: int = 120

    mail_max_rows_per_source: int = 50
    mail_aggregate_row_cap: int = 2000
    mail_max_prompt_chars: int = 30000
    mail_send_retries: int = 3

    bootstrap_org_name: str = "Dossier"
    bootstrap_department_name: str = "General"
    bootstrap_admin_email: EmailStr = "admin@example.com"
    bootstrap_admin_full_name: str = "Platform Administrator"

    @field_validator("jwt_secret")
    @classmethod
    def _validate_jwt_secret(cls, value: str) -> str:
        if len(value.encode("utf-8")) < 32:
            raise ValueError("JWT_SECRET must be at least 32 bytes")
        return value

    @field_validator("credential_encryption_keys")
    @classmethod
    def _validate_credential_keys(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("CREDENTIAL_ENCRYPTION_KEYS is required")
        for entry in value.split(","):
            key_id, separator, key = entry.partition(":")
            if not separator or not key_id.strip() or not key.strip():
                raise ValueError(
                    "CREDENTIAL_ENCRYPTION_KEYS entries must be key_id:fernet_key"
                )
            try:
                Fernet(key.strip().encode())
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f"Invalid Fernet key for key id {key_id.strip()}"
                ) from exc
        return value

    @model_validator(mode="after")
    def _active_key_exists(self) -> "Settings":
        ids = {
            entry.partition(":")[0].strip()
            for entry in self.credential_encryption_keys.split(",")
        }
        if self.credential_encryption_active_key_id not in ids:
            raise ValueError(
                "CREDENTIAL_ENCRYPTION_ACTIVE_KEY_ID must match a configured key"
            )
        return self

    @property
    def credential_key_map(self) -> dict[str, bytes]:
        """Map of key id to raw Fernet key."""
        mapping: dict[str, bytes] = {}
        for entry in self.credential_encryption_keys.split(","):
            key_id, _, key = entry.partition(":")
            mapping[key_id.strip()] = key.strip().encode()
        return mapping

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def allow_secure_cookies(self) -> bool:
        return self.cookie_secure or self.is_production


@lru_cache
def get_settings() -> Settings:
    return Settings()
