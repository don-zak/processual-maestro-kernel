from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from processual_api.auth.account_recovery_service import (
    ACCOUNT_RECOVERY_COMPLETION_TOKEN_PURPOSE,
    ACCOUNT_RECOVERY_MAX_ATTEMPTS,
    ACCOUNT_RECOVERY_PURPOSE,
    ACCOUNT_RECOVERY_VERIFICATION_TOKEN_PURPOSE,
    AccountRecoveryDeniedError,
    AccountRecoveryService,
)

NOW = datetime(2026, 7, 23, 17, 0, tzinfo=UTC)


@dataclass(frozen=True)
class GeneratedToken:
    raw: str
    digest: str


class FakeTokenDigester:
    def __init__(self) -> None:
        self.generated: list[str] = []
        self.digested: list[tuple[str, str]] = []
        self._counter = 0

    def generate_token(
        self,
        *,
        purpose: str,
    ) -> GeneratedToken:
        self._counter += 1
        self.generated.append(purpose)

        raw = f"{purpose}-raw-{self._counter}"
        digest = f"{purpose}-digest-{self._counter}"

        return GeneratedToken(
            raw=raw,
            digest=digest,
        )

    def digest(
        self,
        raw_token: str,
        *,
        purpose: str,
    ) -> str:
        self.digested.append((raw_token, purpose))

        if not raw_token or raw_token == "malformed":
            raise ValueError("invalid token")

        if raw_token.startswith("wrong"):
            return "wrong-digest"

        if raw_token.startswith(ACCOUNT_RECOVERY_VERIFICATION_TOKEN_PURPOSE):
            return ACCOUNT_RECOVERY_VERIFICATION_TOKEN_PURPOSE + "-digest-1"

        return f"{purpose}-digest-from-{raw_token}"


class FakeDeliverySink:
    def __init__(self) -> None:
        self.deliveries: list[dict[str, object]] = []

    async def deliver_verification(self, **values) -> None:
        self.deliveries.append(values)


class FakeRepository:
    def __init__(
        self,
        *,
        principal=None,
        request=None,
    ) -> None:
        self.principal = principal
        self.request = request
        self.invalidations: list[dict[str, object]] = []
        self.added_requests: list[dict[str, object]] = []

    async def eligible_principal_by_login(
        self,
        *,
        login_normalized: str,
    ):
        self.last_login_normalized = login_normalized
        return self.principal

    async def invalidate_active_requests(
        self,
        *,
        user_id,
        invalidated_at,
    ) -> int:
        self.invalidations.append(
            {
                "user_id": user_id,
                "invalidated_at": invalidated_at,
            }
        )
        return 1

    def add_request(self, **values):
        self.added_requests.append(values)
        return values

    async def request_for_update(
        self,
        *,
        request_id,
    ):
        self.requested_id = request_id
        return self.request


class FakeUnitOfWork:
    def __init__(
        self,
        repository: FakeRepository,
    ) -> None:
        self.repository = repository
        self.commit_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False

    async def commit(self) -> None:
        self.commit_count += 1


def _principal(
    *,
    user_status: str = "active",
    recovery_status: str = "verified",
    verified: bool = True,
    revoked: bool = False,
):
    user = SimpleNamespace(
        id=uuid4(),
        status=user_status,
    )
    recovery_email = SimpleNamespace(
        id=uuid4(),
        user_id=user.id,
        purpose="recovery",
        status=recovery_status,
        email_normalized="recovery@example.com",
        verified_at=NOW if verified else None,
        revoked_at=NOW if revoked else None,
    )
    return user, recovery_email


def _request(
    *,
    state: str = "pending",
    token_hash: str | None = None,
    expires_at: datetime | None = None,
    attempt_count: int = 0,
):
    return SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        purpose=ACCOUNT_RECOVERY_PURPOSE,
        state=state,
        verification_token_hash=(token_hash or (ACCOUNT_RECOVERY_VERIFICATION_TOKEN_PURPOSE + "-digest-1")),
        completion_token_hash=None,
        attempt_count=attempt_count,
        expires_at=expires_at or (NOW + timedelta(minutes=30)),
        verified_at=None,
        completed_at=None,
        revoked_at=None,
        updated_at=NOW,
    )


def _service(
    repository: FakeRepository,
    *,
    digester: FakeTokenDigester | None = None,
    delivery: FakeDeliverySink | None = None,
    max_attempts: int = ACCOUNT_RECOVERY_MAX_ATTEMPTS,
):
    unit = FakeUnitOfWork(repository)
    token_digester = digester or FakeTokenDigester()
    delivery_sink = delivery or FakeDeliverySink()

    service = AccountRecoveryService(
        unit_of_work_factory=lambda: unit,
        token_digester=token_digester,
        delivery_sink=delivery_sink,
        clock=lambda: NOW,
        max_attempts=max_attempts,
    )

    return service, unit, token_digester, delivery_sink


@pytest.mark.asyncio
async def test_start_is_enumeration_resistant_for_unknown_account() -> None:
    repository = FakeRepository(principal=None)
    service, unit, digester, delivery = _service(repository)

    receipt = await service.start(
        login=" Unknown@Example.COM ",
    )

    assert repository.last_login_normalized == "unknown@example.com"
    assert receipt.accepted is True
    assert receipt.externally_indistinguishable is True
    assert receipt.session_created is False
    assert receipt.access_token_issued is False
    assert receipt.refresh_token_issued is False
    assert repository.added_requests == []
    assert repository.invalidations == []
    assert delivery.deliveries == []
    assert unit.commit_count == 0
    assert digester.generated == [ACCOUNT_RECOVERY_VERIFICATION_TOKEN_PURPOSE]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "user_status",
        "recovery_status",
        "verified",
        "revoked",
    ),
    [
        ("disabled", "verified", True, False),
        ("active", "pending", False, False),
        ("active", "verified", False, False),
        ("active", "verified", True, True),
    ],
)
async def test_start_hides_ineligible_recovery_principals(
    user_status: str,
    recovery_status: str,
    verified: bool,
    revoked: bool,
) -> None:
    repository = FakeRepository(
        principal=_principal(
            user_status=user_status,
            recovery_status=recovery_status,
            verified=verified,
            revoked=revoked,
        )
    )
    service, unit, _, delivery = _service(repository)

    receipt = await service.start(
        login="person@example.com",
    )

    assert receipt.accepted is True
    assert receipt.externally_indistinguishable is True
    assert repository.added_requests == []
    assert repository.invalidations == []
    assert delivery.deliveries == []
    assert unit.commit_count == 0


@pytest.mark.asyncio
async def test_start_persists_hash_only_and_delivers_raw_transiently() -> None:
    user, recovery_email = _principal()
    repository = FakeRepository(principal=(user, recovery_email))
    service, unit, digester, delivery = _service(repository)

    receipt = await service.start(
        login="Person@Example.com",
    )

    assert receipt.accepted is True
    assert receipt.session_created is False
    assert len(repository.invalidations) == 1
    assert len(repository.added_requests) == 1
    assert unit.commit_count == 1
    assert len(delivery.deliveries) == 1

    persisted = repository.added_requests[0]
    delivered = delivery.deliveries[0]

    assert persisted["user_id"] == user.id
    assert persisted["recovery_email_id"] == recovery_email.id
    assert persisted["purpose"] == ACCOUNT_RECOVERY_PURPOSE
    assert persisted["state"] == "pending"
    assert persisted["verification_token_hash"].endswith("-digest-1")
    assert "raw_token" not in persisted
    assert "token" not in persisted
    assert persisted["completion_token_hash"] is None
    assert persisted["attempt_count"] == 0

    assert delivered["raw_token"].endswith("-raw-1")
    assert delivered["recovery_email_normalized"] == (recovery_email.email_normalized)
    assert delivered["raw_token"] != (persisted["verification_token_hash"])
    assert digester.generated == [ACCOUNT_RECOVERY_VERIFICATION_TOKEN_PURPOSE]


@pytest.mark.asyncio
async def test_verify_rejects_unknown_request_generically() -> None:
    repository = FakeRepository(request=None)
    service, unit, _, _ = _service(repository)

    with pytest.raises(
        AccountRecoveryDeniedError,
        match="unavailable",
    ):
        await service.verify(
            request_id=uuid4(),
            raw_token=(ACCOUNT_RECOVERY_VERIFICATION_TOKEN_PURPOSE + "-raw-1"),
        )

    assert unit.commit_count == 0


@pytest.mark.asyncio
async def test_verify_rejects_malformed_token_generically() -> None:
    repository = FakeRepository(request=_request())
    service, unit, _, _ = _service(repository)

    with pytest.raises(
        AccountRecoveryDeniedError,
        match="unavailable",
    ):
        await service.verify(
            request_id=uuid4(),
            raw_token="malformed",
        )

    assert unit.commit_count == 0


@pytest.mark.asyncio
async def test_verify_increments_attempts_without_disclosing_reason() -> None:
    request = _request(attempt_count=1)
    repository = FakeRepository(request=request)
    service, unit, _, _ = _service(repository)

    with pytest.raises(
        AccountRecoveryDeniedError,
        match="unavailable",
    ):
        await service.verify(
            request_id=request.id,
            raw_token="wrong-token",
        )

    assert request.attempt_count == 2
    assert request.state == "pending"
    assert request.revoked_at is None
    assert unit.commit_count == 1


@pytest.mark.asyncio
async def test_verify_revokes_at_attempt_limit() -> None:
    request = _request(attempt_count=4)
    repository = FakeRepository(request=request)
    service, unit, _, _ = _service(
        repository,
        max_attempts=5,
    )

    with pytest.raises(AccountRecoveryDeniedError):
        await service.verify(
            request_id=request.id,
            raw_token="wrong-token",
        )

    assert request.attempt_count == 5
    assert request.state == "revoked"
    assert request.revoked_at == NOW
    assert unit.commit_count == 1


@pytest.mark.asyncio
async def test_verify_marks_expired_request() -> None:
    request = _request(
        expires_at=NOW,
    )
    repository = FakeRepository(request=request)
    service, unit, _, _ = _service(repository)

    with pytest.raises(AccountRecoveryDeniedError):
        await service.verify(
            request_id=request.id,
            raw_token=(ACCOUNT_RECOVERY_VERIFICATION_TOKEN_PURPOSE + "-raw-1"),
        )

    assert request.state == "expired"
    assert unit.commit_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state",
    [
        "verified",
        "completed",
        "expired",
        "revoked",
    ],
)
async def test_verify_rejects_non_pending_request(
    state: str,
) -> None:
    request = _request(state=state)
    repository = FakeRepository(request=request)
    service, unit, _, _ = _service(repository)

    with pytest.raises(AccountRecoveryDeniedError):
        await service.verify(
            request_id=request.id,
            raw_token=(ACCOUNT_RECOVERY_VERIFICATION_TOKEN_PURPOSE + "-raw-1"),
        )

    assert unit.commit_count == 0


@pytest.mark.asyncio
async def test_verify_issues_completion_credential_without_session() -> None:
    request = _request()
    repository = FakeRepository(request=request)
    service, unit, digester, _ = _service(repository)

    receipt = await service.verify(
        request_id=request.id,
        raw_token=(ACCOUNT_RECOVERY_VERIFICATION_TOKEN_PURPOSE + "-raw-1"),
    )

    assert receipt.request_id == request.id
    assert receipt.completion_token.endswith("-raw-1")
    assert receipt.completion_expires_at == (NOW + timedelta(minutes=15))
    assert receipt.session_created is False
    assert receipt.access_token_issued is False
    assert receipt.refresh_token_issued is False
    assert receipt.password_change_required is True
    assert receipt.mfa_reenrollment_required is True

    assert request.state == "verified"
    assert request.verified_at == NOW
    assert request.completion_token_hash.endswith("-digest-1")
    assert request.expires_at == receipt.completion_expires_at
    assert request.completion_token_hash != (receipt.completion_token)
    assert unit.commit_count == 1
    assert digester.generated == [ACCOUNT_RECOVERY_COMPLETION_TOKEN_PURPOSE]


def test_constructor_rejects_weakened_limits() -> None:
    repository = FakeRepository()
    unit = FakeUnitOfWork(repository)
    digester = FakeTokenDigester()
    delivery = FakeDeliverySink()

    with pytest.raises(ValueError):
        AccountRecoveryService(
            unit_of_work_factory=lambda: unit,
            token_digester=digester,
            delivery_sink=delivery,
            verification_ttl=timedelta(0),
        )

    with pytest.raises(ValueError):
        AccountRecoveryService(
            unit_of_work_factory=lambda: unit,
            token_digester=digester,
            delivery_sink=delivery,
            completion_ttl=timedelta(0),
        )

    with pytest.raises(ValueError):
        AccountRecoveryService(
            unit_of_work_factory=lambda: unit,
            token_digester=digester,
            delivery_sink=delivery,
            max_attempts=0,
        )


def test_clock_must_be_timezone_aware() -> None:
    repository = FakeRepository()
    unit = FakeUnitOfWork(repository)

    service = AccountRecoveryService(
        unit_of_work_factory=lambda: unit,
        token_digester=FakeTokenDigester(),
        delivery_sink=FakeDeliverySink(),
        clock=lambda: datetime(2026, 7, 23, 17, 0),
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        service._now()


def test_public_receipts_do_not_contain_authentication_tokens() -> None:
    from dataclasses import fields

    from processual_api.auth.account_recovery_service import (
        AccountRecoveryStartReceipt,
        AccountRecoveryVerificationReceipt,
    )

    start_fields = {field.name for field in fields(AccountRecoveryStartReceipt)}
    verification_fields = {field.name for field in fields(AccountRecoveryVerificationReceipt)}

    assert "session" not in start_fields
    assert "access_token" not in start_fields
    assert "refresh_token" not in start_fields

    assert "session" not in verification_fields
    assert "access_token" not in verification_fields
    assert "refresh_token" not in verification_fields
    assert "completion_token" in verification_fields


def test_request_identifier_type_is_uuid() -> None:
    request_id = uuid4()

    assert isinstance(request_id, UUID)
