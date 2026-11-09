"""Fixed-window login limiting backed by Redis.

Rate limiting is a defence-in-depth control, not an authorisation boundary, so a Redis
outage fails open with a warning rather than locking every user out.
"""

import hashlib
import logging

from fastapi import Request

from app.auth.schemas import LoginRequest
from app.config import get_settings
from app.core.exceptions import RateLimitedError
from app.core.redis import get_redis

logger = logging.getLogger(__name__)


def _key(request: Request, email: str) -> str:
    client_ip = request.client.host if request.client else "unknown"
    email_digest = hashlib.sha256(email.strip().lower().encode()).hexdigest()[:16]
    return f"rl:login:{client_ip}:{email_digest}"


async def enforce_login_rate_limit(payload: LoginRequest, request: Request) -> None:
    settings = get_settings()
    key = _key(request, str(payload.email))
    try:
        client = get_redis()
        attempts = await client.incr(key)
        if attempts == 1:
            await client.expire(key, settings.rate_limit_login_window_seconds)
        if attempts > settings.rate_limit_login_attempts:
            raise RateLimitedError("Too many login attempts. Try again shortly.")
    except RateLimitedError:
        raise
    except Exception:  # pragma: no cover - exercised only when Redis is unavailable
        logger.warning("Login rate limiter unavailable; allowing request", exc_info=True)


async def reset_login_rate_limit(payload: LoginRequest, request: Request) -> None:
    try:
        await get_redis().delete(_key(request, str(payload.email)))
    except Exception:  # pragma: no cover
        logger.warning("Could not clear login rate limit", exc_info=True)
