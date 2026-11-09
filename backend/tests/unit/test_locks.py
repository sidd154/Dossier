import pytest

from app.core import locks
from app.core.exceptions import ConflictError


class FakeLockRedis:
    def __init__(self) -> None:
        self.keys: set[str] = set()

    async def set(
        self, key: str, _value: str, *, nx: bool = False, ex: int | None = None
    ) -> bool | None:
        if nx and key in self.keys:
            return None
        self.keys.add(key)
        return True

    async def delete(self, key: str) -> None:
        self.keys.discard(key)


class BrokenRedis:
    async def set(self, *_args: object, **_kwargs: object) -> bool:
        raise ConnectionError("redis down")


async def test_lock_is_held_then_released(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeLockRedis()
    monkeypatch.setattr(locks, "get_redis", lambda: fake)

    async with locks.exclusive_lock("sync:one"):
        assert "sync:one" in fake.keys

    assert "sync:one" not in fake.keys


async def test_overlapping_lock_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeLockRedis()
    monkeypatch.setattr(locks, "get_redis", lambda: fake)

    async with locks.exclusive_lock("sync:one"):
        with pytest.raises(ConflictError):
            async with locks.exclusive_lock("sync:one"):
                pass


async def test_lock_fails_open_when_redis_is_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(locks, "get_redis", lambda: BrokenRedis())

    async with locks.exclusive_lock("sync:one"):
        passed = True

    assert passed
