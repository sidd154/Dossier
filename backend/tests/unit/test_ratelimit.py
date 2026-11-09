import pytest
from starlette.requests import Request

from app.auth import ratelimit
from app.auth.schemas import LoginRequest
from app.config import get_settings
from app.core.exceptions import RateLimitedError


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.expiries: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def expire(self, key: str, seconds: int) -> None:
        self.expiries[key] = seconds

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)

    async def ttl(self, key: str) -> int:
        return self.expiries.get(key, 0)


class BrokenRedis:
    async def incr(self, key: str) -> int:
        raise ConnectionError("redis down")


def _request(ip: str = "10.0.0.1") -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "server": ("test", 80),
            "client": (ip, 1234),
        }
    )


def _payload(email: str = "person@example.com") -> LoginRequest:
    return LoginRequest(email=email, password="irrelevant-but-long")


async def test_limit_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis()
    monkeypatch.setattr(ratelimit, "get_redis", lambda: fake)

    settings = get_settings()
    for _ in range(settings.rate_limit_login_attempts):
        await ratelimit.enforce_login_rate_limit(_payload(), _request())

    with pytest.raises(RateLimitedError):
        await ratelimit.enforce_login_rate_limit(_payload(), _request())


async def test_limit_is_scoped_per_email_and_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis()
    monkeypatch.setattr(ratelimit, "get_redis", lambda: fake)
    settings = get_settings()

    for _ in range(settings.rate_limit_login_attempts):
        await ratelimit.enforce_login_rate_limit(_payload("a@example.com"), _request())

    # A different email from the same IP has its own window.
    await ratelimit.enforce_login_rate_limit(_payload("b@example.com"), _request())


async def test_redis_outage_fails_open(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ratelimit, "get_redis", lambda: BrokenRedis())
    await ratelimit.enforce_login_rate_limit(_payload(), _request())


async def test_successful_login_clears_the_counter(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis()
    monkeypatch.setattr(ratelimit, "get_redis", lambda: fake)
    await ratelimit.enforce_login_rate_limit(_payload(), _request())
    await ratelimit.reset_login_rate_limit(_payload(), _request())
    assert fake.values == {}
