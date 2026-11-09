"""Test harness.

A session-scoped subprocess applies migrations to the test database. Each test then
opens an outer transaction and lets the application commit into savepoints, so every
test is fully isolated without truncating tables.
"""

import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth.ratelimit import enforce_login_rate_limit, reset_login_rate_limit
from app.config import get_settings
from app.core.exceptions import AppError
from app.core.redis import get_redis
from app.core.security import hash_password
from app.database.session import get_db
from app.departments.models import Department
from app.main import create_app
from app.organisation.models import ORGANISATION_ID, Organisation
from app.users.models import AccountStatus, AppUser, UserRole

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PASSWORD = "Test-Password-123!"
_PASSWORD_HASH = hash_password(DEFAULT_PASSWORD)


@pytest.fixture(autouse=True)
def isolated_redis(monkeypatch: pytest.MonkeyPatch):
    """The rate limiter owns a process-wide Redis client bound to one event loop.

    Tests create a fresh loop each time, and the login handler calls the reset helper
    directly rather than through dependency injection, so neutralise it here.
    """

    async def noop(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr("app.auth.router.reset_login_rate_limit", noop)
    monkeypatch.setattr("app.auth.router.enforce_login_rate_limit", noop)
    get_redis.cache_clear()
    yield
    get_redis.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def apply_migrations() -> None:
    settings = get_settings()
    url = settings.test_database_url or settings.database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": url},
        check=True,
        capture_output=True,
    )


@pytest_asyncio.fixture
async def db_engine():
    settings = get_settings()
    url = settings.test_database_url or settings.database_url
    engine = create_async_engine(url, poolclass=NullPool)
    yield engine
    await engine.dispose()


_TRUNCATE = text(
    "TRUNCATE TABLE mail_delivery, mail_execution, mail_schedule_source, "
    "mail_schedule, mail_template, mail_settings, sync_job, snapshot_record, snapshot, "
    "data_source_permission, data_source, connector_credential, connector, "
    "audit_log, refresh_token, app_user, department, organisation "
    "RESTART IDENTITY CASCADE"
)


@pytest_asyncio.fixture
async def session(db_engine) -> AsyncIterator[AsyncSession]:
    """A real session, with the database emptied after every test.

    Services commit normally, so an outer-transaction wrapper would need savepoint
    gymnastics that are easy to get subtly wrong. Truncation is explicit and provable.
    """
    db_session = AsyncSession(bind=db_engine, expire_on_commit=False)
    try:
        yield db_session
    finally:
        await db_session.close()
        async with db_engine.begin() as connection:
            await connection.execute(_TRUNCATE)


@pytest_asyncio.fixture
async def app(session: AsyncSession):
    application = create_app()

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        try:
            yield session
        except AppError:
            # Expected 4xx outcomes leave no pending writes, and rolling back would
            # expire the ORM objects the test itself is holding.
            raise
        except Exception:
            await session.rollback()
            raise

    application.dependency_overrides[get_db] = override_get_db
    # Redis is irrelevant to most tests and shared between runs; opt out by default.
    application.dependency_overrides[enforce_login_rate_limit] = lambda: None
    application.dependency_overrides[reset_login_rate_limit] = lambda: None

    yield application
    application.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


@pytest.fixture
def fake_connector(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Swap the real adapters for a deterministic fake.

    Returns a mutable holder so a test can replace the connector mid-test, e.g. to
    simulate an upstream failure after a successful sync.
    """
    from contextlib import asynccontextmanager

    from tests.fakes import FakeConnector

    @asynccontextmanager
    async def no_lock(*_args: object, **_kwargs: object):
        yield

    monkeypatch.setattr("app.sync.service.exclusive_lock", no_lock)

    holder: dict[str, object] = {"connector": FakeConnector()}
    monkeypatch.setattr(
        "app.sync.service.get_connector", lambda *_a, **_k: holder["connector"]
    )
    monkeypatch.setattr(
        "app.data_sources.service.build_adapter", lambda _connector: holder["connector"]
    )
    monkeypatch.setattr(
        "app.connectors.service.build_adapter", lambda _connector: holder["connector"]
    )
    return holder


@pytest.fixture
def fake_smtp(monkeypatch: pytest.MonkeyPatch) -> list:
    """Capture messages instead of opening an SMTP connection."""
    from app.mail import sender

    sent: list = []

    def fake_send(_config, message) -> None:
        sent.append(message)

    monkeypatch.setattr(sender, "_send_sync", fake_send)
    return sent


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch):
    from tests.fakes import FakeLLM

    llm = FakeLLM()
    monkeypatch.setattr("app.mail.preview_service.get_llm_provider", lambda: llm)
    monkeypatch.setattr("app.mail.execution.get_llm_provider", lambda: llm)
    return llm


@pytest_asyncio.fixture
async def raw_client() -> AsyncIterator[AsyncClient]:
    """A client with no dependency overrides and empty cookies."""
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


# ---------------------------------------------------------------- factories


async def make_department(
    session: AsyncSession,
    *,
    name: str | None = None,
    is_active: bool = True,
) -> Department:
    name = name or f"Department {uuid.uuid4().hex[:8]}"
    department = Department(
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:6]}",
        is_active=is_active,
    )
    session.add(department)
    await session.commit()
    return department


async def make_user(
    session: AsyncSession,
    *,
    email: str | None = None,
    department: Department | None = None,
    full_name: str = "Test User",
    role: UserRole = UserRole.USER,
    status: AccountStatus = AccountStatus.ACTIVE,
    must_change_password: bool = False,
    password: str = DEFAULT_PASSWORD,
) -> AppUser:
    department = department or await make_department(session)
    user = AppUser(
        email=email or f"user-{uuid.uuid4().hex[:8]}@example.com",
        full_name=full_name,
        hashed_password=_PASSWORD_HASH if password == DEFAULT_PASSWORD else hash_password(password),
        role=role,
        status=status,
        department_id=department.id,
        must_change_password=must_change_password,
    )
    session.add(user)
    await session.commit()
    return user


async def make_organisation(
    session: AsyncSession, *, name: str = "Acme Ltd"
) -> Organisation:
    organisation = await session.get(Organisation, ORGANISATION_ID)
    if organisation is None:
        organisation = Organisation(
            id=ORGANISATION_ID,
            name=name,
            locations=[],
            timezone="UTC",
            extra_metadata={},
        )
        session.add(organisation)
        await session.commit()
    return organisation


async def login(client: AsyncClient, email: str, password: str = DEFAULT_PASSWORD):
    return await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )


async def make_source_snapshot(
    session: AsyncSession,
    *,
    name: str,
    rows: list[dict],
    columns: list[str] | None = None,
    department: Department | None = None,
    grant: bool = True,
):
    """Create a connector, data source, and READY snapshot without any network."""
    from app.connectors.models import Connector, ConnectorType
    from app.data_sources.models import DataSource, DataSourcePermission
    from app.snapshots.models import Snapshot, SnapshotRecord, SnapshotStatus

    connector = Connector(
        name=f"Connector {uuid.uuid4().hex[:8]}",
        type=ConnectorType.GOOGLE_SHEETS,
        is_active=True,
        config={},
    )
    session.add(connector)
    await session.flush()

    source = DataSource(
        connector_id=connector.id,
        external_id=f"ext-{uuid.uuid4().hex[:8]}",
        name=name,
        kind="sheet",
        config={},
        is_active=True,
    )
    session.add(source)
    await session.flush()

    column_names = columns or (list(rows[0].keys()) if rows else [])
    snapshot = Snapshot(
        data_source_id=source.id,
        status=SnapshotStatus.READY,
        record_count=len(rows),
        schema_hash="0" * 64,
        source_metadata={"columns": column_names},
    )
    session.add(snapshot)
    await session.flush()

    for index, row in enumerate(rows):
        session.add(
            SnapshotRecord(
                snapshot_id=snapshot.id,
                row_index=index,
                external_id=None,
                payload=row,
            )
        )

    source.current_snapshot_id = snapshot.id
    if department is not None and grant:
        session.add(
            DataSourcePermission(
                department_id=department.id,
                data_source_id=source.id,
                granted_by=None,
            )
        )
    await session.commit()
    return source


async def configure_mail_settings(
    session: AsyncSession,
    *,
    host: str = "smtp.test",
    port: int = 25,
    from_email: str = "noreply@example.com",
    from_name: str = "Dossier",
):
    from app.mail.models import MAIL_SETTINGS_ID, MailSettings, SmtpSecurity

    row = await session.get(MailSettings, MAIL_SETTINGS_ID)
    if row is None:
        row = MailSettings(
            id=MAIL_SETTINGS_ID,
            host=host,
            port=port,
            from_email=from_email,
            from_name=from_name,
            security=SmtpSecurity.NONE,
        )
        session.add(row)
        await session.commit()
    return row
