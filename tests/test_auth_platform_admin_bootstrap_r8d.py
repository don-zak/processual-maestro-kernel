from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from processual_api.auth.platform_admin_bootstrap_repository import (
    PLATFORM_ADMIN_BOOTSTRAP_LOCK_ID,
    SqlAlchemyPlatformAdminBootstrapRepository,
)
from processual_api.auth.platform_admin_bootstrap_service import (
    PlatformAdminAlreadyBootstrappedError,
    PlatformAdminBootstrapCommand,
    PlatformAdminBootstrapDeniedError,
    PlatformAdminBootstrapEmailConflictError,
    PlatformAdminBootstrapService,
)

BOOTSTRAP_SECRET = (
    "pmk-first-admin-bootstrap-secret-"
    "with-high-entropy-2026"
)
BOOTSTRAP_SECRET_HASH = hashlib.sha256(
    BOOTSTRAP_SECRET.encode("utf-8")
).hexdigest()


class PasswordService:
    def __init__(self) -> None:
        self.passwords = []

    def hash_password(self, password: str) -> str:
        self.passwords.append(password)
        return "$argon2id$bootstrap-test-hash"


class FakeRepository:
    def __init__(
        self,
        *,
        authority_exists: bool = False,
        email_exists: bool = False,
    ) -> None:
        self.authority_exists = authority_exists
        self.existing_email = email_exists
        self.lock_acquired = False
        self.calls = []
        self.added = None

    async def acquire_bootstrap_lock(self) -> None:
        self.calls.append("lock")
        self.lock_acquired = True

    async def platform_admin_authority_exists(
        self,
    ) -> bool:
        self.calls.append("authority_exists")
        assert self.lock_acquired is True
        return self.authority_exists

    async def email_exists(self, email) -> bool:
        self.calls.append("email_exists")
        assert self.lock_acquired is True
        return self.existing_email

    def add_first_platform_admin(
        self,
        **values,
    ) -> None:
        self.calls.append("add")
        assert self.lock_acquired is True
        self.added = values


class FakeUnitOfWork:
    def __init__(self, repository) -> None:
        self.repository = repository
        self.commits = 0
        self.exits = []

    async def __aenter__(self):
        return self

    async def commit(self):
        self.commits += 1

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        self.exits.append(exc_type)


def _service(
    repository,
    *,
    now=None,
    password_service=None,
):
    unit = FakeUnitOfWork(repository)
    password_authority = (
        password_service or PasswordService()
    )
    user_id = uuid.UUID(
        "11111111-1111-1111-1111-111111111111"
    )
    authority_id = uuid.UUID(
        "22222222-2222-2222-2222-222222222222"
    )
    service = PlatformAdminBootstrapService(
        unit_of_work_factory=lambda: unit,
        password_service=password_authority,
        expected_secret_sha256=BOOTSTRAP_SECRET_HASH,
        clock=lambda: (
            now
            or datetime(
                2026,
                7,
                22,
                20,
                0,
                tzinfo=UTC,
            )
        ),
        user_id_factory=lambda: user_id,
        authority_id_factory=lambda: authority_id,
    )
    return (
        service,
        unit,
        password_authority,
        user_id,
        authority_id,
    )


def _command(
    *,
    secret=BOOTSTRAP_SECRET,
    email=" First.Admin@Example.COM ",
):
    return PlatformAdminBootstrapCommand(
        email=email,
        display_name=" First Administrator ",
        password=(
            "A-strong-and-unique-bootstrap-"
            "password-2026!"
        ),
        bootstrap_secret=secret,
    )


def _compiled_sql(statement) -> str:
    return " ".join(
        str(
            statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={
                    "literal_binds": True,
                },
            )
        ).split()
    )


def test_bootstrap_creates_active_verified_identity_and_authority():
    repository = FakeRepository()
    (
        service,
        unit,
        password_service,
        user_id,
        authority_id,
    ) = _service(repository)

    receipt = asyncio.run(
        service.bootstrap(_command())
    )

    assert receipt.user_id == user_id
    assert (
        receipt.email_normalized
        == "first.admin@example.com"
    )
    assert receipt.authority == "platform_admin"
    assert receipt.mfa_required is True
    assert receipt.session_issued is False

    assert unit.commits == 1
    assert repository.calls == [
        "lock",
        "authority_exists",
        "email_exists",
        "add",
    ]

    persisted = repository.added
    assert persisted is not None
    assert persisted["authority_id"] == authority_id
    assert (
        persisted["email_normalized"]
        == "first.admin@example.com"
    )
    assert (
        persisted["display_name"]
        == "First Administrator"
    )
    assert persisted["password_hash"].startswith(
        "$argon2id$"
    )
    assert len(password_service.passwords) == 1
    assert (
        password_service.passwords[0]
        == _command().password
    )


def test_bootstrap_rejects_invalid_secret_before_database_access():
    repository = FakeRepository()
    service, unit, _, _, _ = _service(repository)

    with pytest.raises(
        PlatformAdminBootstrapDeniedError
    ):
        asyncio.run(
            service.bootstrap(
                _command(secret="incorrect-secret")
            )
        )

    assert repository.calls == []
    assert repository.added is None
    assert unit.commits == 0


@pytest.mark.parametrize(
    "authority_exists",
    (True,),
)
def test_bootstrap_refuses_when_any_platform_admin_record_exists(
    authority_exists,
):
    repository = FakeRepository(
        authority_exists=authority_exists
    )
    service, unit, _, _, _ = _service(repository)

    with pytest.raises(
        PlatformAdminAlreadyBootstrappedError
    ):
        asyncio.run(service.bootstrap(_command()))

    assert repository.calls == [
        "lock",
        "authority_exists",
    ]
    assert repository.added is None
    assert unit.commits == 0


def test_bootstrap_refuses_existing_identity_email():
    repository = FakeRepository(
        email_exists=True
    )
    service, unit, _, _, _ = _service(repository)

    with pytest.raises(
        PlatformAdminBootstrapEmailConflictError
    ):
        asyncio.run(service.bootstrap(_command()))

    assert repository.calls == [
        "lock",
        "authority_exists",
        "email_exists",
    ]
    assert repository.added is None
    assert unit.commits == 0


def test_bootstrap_requires_timezone_aware_clock():
    repository = FakeRepository()
    service, unit, _, _, _ = _service(
        repository,
        now=datetime(2026, 7, 22, 20, 0),
    )

    with pytest.raises(ValueError):
        asyncio.run(service.bootstrap(_command()))

    assert repository.calls == []
    assert unit.commits == 0


@pytest.mark.parametrize(
    "digest",
    (
        "",
        "not-a-sha256",
        "f" * 63,
        "g" * 64,
    ),
)
def test_bootstrap_rejects_invalid_expected_secret_digest(
    digest,
):
    with pytest.raises(ValueError):
        PlatformAdminBootstrapService(
            unit_of_work_factory=lambda: object(),
            password_service=PasswordService(),
            expected_secret_sha256=digest,
        )


def test_repository_uses_transaction_scoped_advisory_lock():
    session = SimpleNamespace()
    repository = (
        SqlAlchemyPlatformAdminBootstrapRepository(
            session
        )
    )

    class ExecuteSession:
        def __init__(self):
            self.statements = []

        async def execute(self, statement):
            self.statements.append(statement)

    execute_session = ExecuteSession()
    repository._session = execute_session

    asyncio.run(repository.acquire_bootstrap_lock())

    assert len(execute_session.statements) == 1
    sql = _compiled_sql(
        execute_session.statements[0]
    )
    assert "pg_advisory_xact_lock" in sql
    assert str(
        PLATFORM_ADMIN_BOOTSTRAP_LOCK_ID
    ) in sql


def test_repository_closes_bootstrap_for_active_or_revoked_authority():
    class ScalarSession:
        def __init__(self):
            self.statements = []

        async def scalar(self, statement):
            self.statements.append(statement)
            return uuid.uuid4()

    session = ScalarSession()
    repository = (
        SqlAlchemyPlatformAdminBootstrapRepository(
            session
        )
    )

    exists = asyncio.run(
        repository.platform_admin_authority_exists()
    )

    assert exists is True
    sql = _compiled_sql(session.statements[0])
    assert (
        "identity_platform_authorities.authority "
        "= 'platform_admin'"
        in sql
    )
    assert (
        "identity_platform_authorities.status "
        "IN ('active', 'revoked')"
        in sql
    )


def test_bootstrap_source_never_issues_session_or_token():
    repository = FakeRepository()
    service, _, _, _, _ = _service(repository)

    receipt = asyncio.run(
        service.bootstrap(_command())
    )

    assert receipt.session_issued is False
    assert not hasattr(receipt, "access_token")
    assert not hasattr(receipt, "refresh_token")
