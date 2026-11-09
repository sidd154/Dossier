import uuid
from types import SimpleNamespace

from app.permissions.context import PermissionContext, build_permission_context
from app.users.models import AccountStatus, UserRole


def test_empty_permission_set_grants_nothing() -> None:
    context = PermissionContext(
        user_id=uuid.uuid4(),
        role=UserRole.ADMIN,
        department_id=uuid.uuid4(),
        allowed_source_ids=frozenset(),
    )
    assert context.can_access_source(uuid.uuid4()) is False
    assert context.allowed_source_ids == frozenset()


def test_context_grants_only_explicit_sources() -> None:
    allowed = uuid.uuid4()
    context = PermissionContext(
        user_id=uuid.uuid4(),
        role=UserRole.USER,
        department_id=uuid.uuid4(),
        allowed_source_ids=frozenset({allowed}),
    )
    assert context.can_access_source(allowed) is True
    assert context.can_access_source(uuid.uuid4()) is False


def test_builder_starts_fail_closed() -> None:
    user = SimpleNamespace(
        id=uuid.uuid4(),
        role=UserRole.ADMIN,
        department_id=uuid.uuid4(),
        status=AccountStatus.ACTIVE,
    )
    context = build_permission_context(user)
    assert context.allowed_source_ids == frozenset()
    assert context.role == UserRole.ADMIN
