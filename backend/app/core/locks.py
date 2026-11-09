"""Redis-backed mutual exclusion for jobs that must not overlap."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.config import get_settings
from app.core.exceptions import ConflictError
from app.core.redis import get_redis

logger = logging.getLogger(__name__)


@asynccontextmanager
async def exclusive_lock(key: str, *, ttl_seconds: int | None = None) -> AsyncIterator[None]:
    """Hold ``key`` for the duration of the block.

    If Redis is unavailable the lock fails open: a duplicate sync cannot corrupt data
    (snapshot promotion is transactional), whereas a hard failure would stall every
    scheduled job during a Redis outage.
    """
    ttl = ttl_seconds or get_settings().sync_lock_ttl_seconds
    client = get_redis()
    try:
        acquired = await client.set(key, "1", nx=True, ex=ttl)
    except Exception:  # pragma: no cover - exercised only when Redis is unavailable
        logger.warning("Lock store unavailable; proceeding without %s", key, exc_info=True)
        yield
        return

    if not acquired:
        raise ConflictError(
            "A sync is already running for this source.", code="sync_in_progress"
        )
    try:
        yield
    finally:
        try:
            await client.delete(key)
        except Exception:  # pragma: no cover
            logger.warning("Could not release lock %s", key, exc_info=True)
