"""Operational commands.

Usage:
    python -m app.cli bootstrap
    python -m app.cli set-password --email ... --password ...
    python -m app.cli seed-demo
"""

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable

from sqlalchemy import select

from app.auth.service import revoke_all_user_tokens
from app.config import get_settings
from app.connectors.models import Connector, ConnectorType
from app.core.security import (
    generate_temporary_password,
    hash_password,
    validate_password_strength,
)
from app.core.text import slugify
from app.data_sources.models import DataSource, DataSourcePermission
from app.database.session import async_session_factory, engine
from app.departments.models import Department
from app.organisation.models import ORGANISATION_ID, Organisation
from app.snapshots.models import Snapshot, SnapshotRecord, SnapshotStatus
from app.sync.service import schema_hash
from app.users.models import AccountStatus, AppUser, UserRole


def _deal(
    name: str, owner: str, stage: str, amount: int, close_date: str
) -> dict[str, object]:
    return {
        "Deal": name,
        "Owner": owner,
        "Stage": stage,
        "Amount": amount,
        "Close Date": close_date,
    }


DEMO_ROWS = [
    _deal("Northwind renewal", "Sam Sales", "Closed won", 42000, "2026-11-01"),
    _deal("Acme expansion", "Sam Sales", "Negotiation", 18500, "2026-11-08"),
    _deal("Globex pilot", "Priya Rao", "Proposal", 9600, "2026-11-15"),
    _deal("Initech licence", "Sam Sales", "Closed won", 27400, "2026-10-28"),
    _deal("Umbrella services", "Priya Rao", "Discovery", 12000, "2026-12-02"),
    _deal("Soylent upgrade", "Alex Kim", "Negotiation", 31000, "2026-11-20"),
]


async def seed_demo() -> int:
    """Create a labelled demo source so mail can run without live connectors."""
    settings = get_settings()
    async with async_session_factory() as session:
        organisation = await session.get(Organisation, ORGANISATION_ID)
        if organisation is None:
            organisation = Organisation(
                id=ORGANISATION_ID,
                name=settings.bootstrap_org_name,
                locations=[],
                timezone="UTC",
                extra_metadata={},
            )
            session.add(organisation)
            await session.flush()

        department = await session.scalar(
            select(Department).where(Department.name == settings.bootstrap_department_name)
        )
        if department is None:
            department = Department(
                name=settings.bootstrap_department_name,
                slug=slugify(settings.bootstrap_department_name, fallback="general"),
                is_active=True,
            )
            session.add(department)
            await session.flush()

        connector = await session.scalar(
            select(Connector).where(Connector.name == "Demo Data")
        )
        if connector is None:
            connector = Connector(
                name="Demo Data",
                type=ConnectorType.GOOGLE_SHEETS,
                is_active=True,
                config={"demo": True},
            )
            session.add(connector)
            await session.flush()

        source = await session.scalar(
            select(DataSource).where(
                DataSource.connector_id == connector.id,
                DataSource.external_id == "demo-sales-pipeline",
            )
        )
        if source is None:
            source = DataSource(
                connector_id=connector.id,
                external_id="demo-sales-pipeline",
                name="Demo Sales Pipeline",
                kind="sheet",
                config={"demo": True},
                is_active=True,
            )
            session.add(source)
            await session.flush()

        if source.current_snapshot_id is None:
            columns = list(DEMO_ROWS[0].keys())
            snapshot = Snapshot(
                data_source_id=source.id,
                status=SnapshotStatus.READY,
                record_count=len(DEMO_ROWS),
                schema_hash=schema_hash(columns),
                source_metadata={"columns": columns, "demo": True},
            )
            session.add(snapshot)
            await session.flush()
            for index, row in enumerate(DEMO_ROWS):
                session.add(
                    SnapshotRecord(
                        snapshot_id=snapshot.id,
                        row_index=index,
                        external_id=None,
                        payload=row,
                    )
                )
            source.current_snapshot_id = snapshot.id

        granted = await session.scalar(
            select(DataSourcePermission).where(
                DataSourcePermission.department_id == department.id,
                DataSourcePermission.data_source_id == source.id,
            )
        )
        if granted is None:
            session.add(
                DataSourcePermission(
                    department_id=department.id,
                    data_source_id=source.id,
                    granted_by=None,
                )
            )

        await session.commit()
        print("Demo data ready")
        print(f"  source:     {source.name}")
        print(f"  rows:       {len(DEMO_ROWS)}")
        print(f"  department: {department.name} (granted)")
        print("")
        print("Configure SMTP for mailhog:1025 (security NONE), then preview a template.")
        return 0


async def bootstrap() -> int:
    settings = get_settings()

    async with async_session_factory() as session:
        organisation = await session.get(Organisation, ORGANISATION_ID)
        if organisation is None:
            organisation = Organisation(
                id=ORGANISATION_ID,
                name=settings.bootstrap_org_name,
                locations=[],
                timezone="UTC",
                extra_metadata={},
            )
            session.add(organisation)
            await session.flush()
            print(f"Created organisation: {organisation.name}")
        else:
            print(f"Organisation already exists: {organisation.name}")

        department = await session.scalar(
            select(Department).where(Department.name == settings.bootstrap_department_name)
        )
        if department is None:
            department = Department(
                name=settings.bootstrap_department_name,
                slug=slugify(settings.bootstrap_department_name, fallback="general"),
                is_active=True,
            )
            session.add(department)
            await session.flush()
            print(f"Created department: {department.name}")
        else:
            print(f"Department already exists: {department.name}")

        existing_admin = await session.scalar(
            select(AppUser).where(AppUser.email == str(settings.bootstrap_admin_email))
        )
        if existing_admin is not None:
            await session.commit()
            print(f"Admin already exists: {existing_admin.email}")
            return 0

        temporary_password = generate_temporary_password()
        admin = AppUser(
            email=str(settings.bootstrap_admin_email).lower(),
            full_name=settings.bootstrap_admin_full_name,
            hashed_password=hash_password(temporary_password),
            role=UserRole.ADMIN,
            status=AccountStatus.ACTIVE,
            department_id=department.id,
            must_change_password=True,
        )
        session.add(admin)
        await session.commit()

        print("")
        print("Administrator created")
        print(f"  email:    {admin.email}")
        print(f"  password: {temporary_password}")
        print("")
        print("This password is shown once and must be changed at first login.")
        return 0


async def set_password(*, email: str, password: str, force_change: bool) -> int:
    """Operator recovery: set a known password without emailing anything."""
    async with async_session_factory() as session:
        user = await session.scalar(
            select(AppUser).where(AppUser.email == email.strip().lower())
        )
        if user is None:
            print(f"No user with email {email}", file=sys.stderr)
            return 1

        try:
            validate_password_strength(password)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        user.hashed_password = hash_password(password)
        user.must_change_password = force_change
        await revoke_all_user_tokens(session, user.id)
        await session.commit()

        print(f"Password updated for {user.email}")
        print(f"  must change at next login: {'yes' if force_change else 'no'}")
        return 0


async def _run_and_dispose(command: Callable[[], Awaitable[int]]) -> int:
    try:
        return await command()
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("bootstrap", help="Create the organisation and first administrator")
    subparsers.add_parser(
        "seed-demo",
        help="Create a demo data source and snapshot so mail can be demonstrated",
    )

    password_parser = subparsers.add_parser(
        "set-password", help="Set a known password for an existing user"
    )
    password_parser.add_argument("--email", required=True)
    password_parser.add_argument("--password", required=True)
    password_parser.add_argument(
        "--force-change",
        action="store_true",
        help="Require the user to change it at next login",
    )
    args = parser.parse_args(argv)

    if args.command == "bootstrap":
        return asyncio.run(_run_and_dispose(bootstrap))

    if args.command == "seed-demo":
        return asyncio.run(_run_and_dispose(seed_demo))

    if args.command == "set-password":
        return asyncio.run(
            _run_and_dispose(
                lambda: set_password(
                    email=args.email,
                    password=args.password,
                    force_change=args.force_change,
                )
            )
        )

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
