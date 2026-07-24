from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from processual_api.auth.delivery_contracts import DeliveryClaim
from processual_api.auth.delivery_crypto import DeliveryPayloadCipher
from processual_api.auth.delivery_dispatcher import (
    DeliveryDispatcher,
    DeliveryDispatcherConfig,
)
from processual_api.auth.delivery_provider import (
    DeliveryProviderError,
    validate_https_endpoint,
)


class FakeRepository:
    def __init__(self, claims=(), *, finalize=True) -> None:
        self.claims = tuple(claims)
        self.finalize = finalize
        self.claim_calls = []
        self.delivered = []
        self.failed = []

    async def claim_batch(self, **values):
        self.claim_calls.append(values)
        return self.claims

    async def mark_delivered(self, **values):
        self.delivered.append(values)
        return self.finalize

    async def mark_failed(self, **values):
        self.failed.append(values)
        return self.finalize


class FakeProvider:
    def __init__(self, error_code=None) -> None:
        self.error_code = error_code
        self.calls = []

    async def send_verification_email(self, **values):
        self.calls.append(values)
        if self.error_code:
            raise DeliveryProviderError(self.error_code)


def _cipher():
    return DeliveryPayloadCipher(current_key_version="v1", keys={"v1": b"k" * 32})


def _claim(*, now, attempt_count=1, user_status="pending_verification", consumed=None, invalidated=None):
    cipher = _cipher()
    outbox_id = uuid.uuid4()
    user_id = uuid.uuid4()
    action_token_id = uuid.uuid4()
    encrypted = cipher.encrypt(
        "raw-verification-token",
        outbox_id=str(outbox_id),
        user_id=str(user_id),
        action_token_id=str(action_token_id),
        purpose="verify_email",
    )
    return DeliveryClaim(
        outbox_id=outbox_id,
        user_id=user_id,
        action_token_id=action_token_id,
        claim_id=uuid.uuid4(),
        recipient_email="person@example.com",
        user_status=user_status,
        event_type="verify_email",
        payload_ciphertext=encrypted.ciphertext,
        payload_key_version=encrypted.key_version,
        action_token_expires_at=now + timedelta(hours=1),
        action_token_consumed_at=consumed,
        action_token_invalidated_at=invalidated,
        attempt_count=attempt_count,
    )


def _recovery_claim(
    *,
    now,
    attempt_count=1,
    user_status="active",
    state="pending",
    revoked_at=None,
    expires_at=None,
):
    cipher = _cipher()
    outbox_id = uuid.uuid4()
    user_id = uuid.uuid4()
    recovery_request_id = uuid.uuid4()

    encrypted = cipher.encrypt(
        "raw-account-recovery-token",
        outbox_id=str(outbox_id),
        user_id=str(user_id),
        account_recovery_request_id=(str(recovery_request_id)),
        purpose="account_recovery_verification",
    )

    return DeliveryClaim(
        outbox_id=outbox_id,
        user_id=user_id,
        action_token_id=None,
        claim_id=uuid.uuid4(),
        recipient_email="recovery@example.com",
        user_status=user_status,
        event_type="account_recovery_verification",
        payload_ciphertext=encrypted.ciphertext,
        payload_key_version=encrypted.key_version,
        action_token_expires_at=None,
        action_token_consumed_at=None,
        action_token_invalidated_at=None,
        attempt_count=attempt_count,
        account_recovery_request_id=(recovery_request_id),
        account_recovery_expires_at=(expires_at or now + timedelta(minutes=30)),
        account_recovery_state=state,
        account_recovery_revoked_at=revoked_at,
    )


def _dispatcher(repository, provider, *, now, max_attempts=3):
    return DeliveryDispatcher(
        repository=repository,
        provider=provider,
        cipher=_cipher(),
        config=DeliveryDispatcherConfig(
            public_base_url="https://accounts.example.test",
            batch_size=10,
            lease_timeout=timedelta(minutes=5),
            max_attempts=max_attempts,
            retry_base=timedelta(seconds=30),
            retry_max=timedelta(minutes=10),
        ),
        clock=lambda: now,
    )


def test_dispatch_success_uses_stable_idempotency_and_marks_claim_delivered():
    now = datetime(2026, 7, 22, 16, tzinfo=UTC)
    claim = _claim(now=now)
    repository = FakeRepository([claim])
    provider = FakeProvider()

    result = asyncio.run(_dispatcher(repository, provider, now=now).dispatch_once())

    assert result.claimed == result.delivered == 1
    assert result.retry_scheduled == result.dead_lettered == result.stale_finalization == 0
    assert provider.calls[0]["recipient"] == "person@example.com"
    assert provider.calls[0]["verification_url"].startswith("https://accounts.example.test/verify-email?token=")
    assert provider.calls[0]["idempotency_key"] == f"pmk-auth-delivery-v1:{claim.outbox_id}"
    assert repository.delivered[0]["claim_id"] == claim.claim_id


def test_account_recovery_dispatch_uses_recovery_authority_and_template():
    now = datetime(2026, 7, 24, 8, tzinfo=UTC)
    claim = _recovery_claim(now=now)
    repository = FakeRepository([claim])
    provider = FakeProvider()

    result = asyncio.run(
        _dispatcher(
            repository,
            provider,
            now=now,
        ).dispatch_once()
    )

    assert result.claimed == 1
    assert result.delivered == 1
    assert result.retry_scheduled == 0
    assert result.dead_lettered == 0

    call = provider.calls[0]

    assert call["template"] == ("account_recovery_verification")
    assert call["recipient"] == ("recovery@example.com")
    assert call["verification_url"].startswith("https://accounts.example.test/auth/account-recovery/verify?token=")
    assert "raw-account-recovery-token" in (call["verification_url"])
    assert repository.delivered[0]["claim_id"] == (claim.claim_id)


@pytest.mark.parametrize(
    ("values", "error_code"),
    (
        (
            {
                "expires_at": datetime(
                    2026,
                    7,
                    24,
                    8,
                    tzinfo=UTC,
                )
            },
            "account_recovery_expired",
        ),
        (
            {"state": "verified"},
            "account_recovery_ineligible",
        ),
        (
            {
                "revoked_at": datetime(
                    2026,
                    7,
                    24,
                    7,
                    59,
                    tzinfo=UTC,
                )
            },
            "account_recovery_revoked",
        ),
    ),
)
def test_ineligible_account_recovery_is_terminal(
    values,
    error_code,
):
    now = datetime(2026, 7, 24, 8, tzinfo=UTC)
    claim = _recovery_claim(
        now=now,
        **values,
    )
    repository = FakeRepository([claim])
    provider = FakeProvider()

    result = asyncio.run(
        _dispatcher(
            repository,
            provider,
            now=now,
        ).dispatch_once()
    )

    assert result.dead_lettered == 1
    assert result.delivered == 0
    assert provider.calls == []
    assert repository.failed[0]["error_code"] == (error_code)


def test_claim_requires_exactly_one_delivery_authority():
    now = datetime(2026, 7, 24, 8, tzinfo=UTC)
    recovery_claim = _recovery_claim(now=now)

    invalid_claim = DeliveryClaim(
        outbox_id=recovery_claim.outbox_id,
        user_id=recovery_claim.user_id,
        action_token_id=uuid.uuid4(),
        claim_id=recovery_claim.claim_id,
        recipient_email=(recovery_claim.recipient_email),
        user_status=recovery_claim.user_status,
        event_type=recovery_claim.event_type,
        payload_ciphertext=(recovery_claim.payload_ciphertext),
        payload_key_version=(recovery_claim.payload_key_version),
        action_token_expires_at=(now + timedelta(minutes=30)),
        action_token_consumed_at=None,
        action_token_invalidated_at=None,
        attempt_count=1,
        account_recovery_request_id=(recovery_claim.account_recovery_request_id),
        account_recovery_expires_at=(recovery_claim.account_recovery_expires_at),
        account_recovery_state="pending",
        account_recovery_revoked_at=None,
    )

    repository = FakeRepository([invalid_claim])
    provider = FakeProvider()

    result = asyncio.run(
        _dispatcher(
            repository,
            provider,
            now=now,
        ).dispatch_once()
    )

    assert result.dead_lettered == 1
    assert provider.calls == []
    assert repository.failed[0]["error_code"] == ("delivery_authority_invalid")


def test_provider_failure_schedules_bounded_retry_without_exposing_payload():
    now = datetime(2026, 7, 22, 16, tzinfo=UTC)
    claim = _claim(now=now, attempt_count=1)
    repository = FakeRepository([claim])
    provider = FakeProvider("provider_5xx")

    result = asyncio.run(_dispatcher(repository, provider, now=now).dispatch_once())

    assert result.retry_scheduled == 1
    assert result.dead_lettered == 0
    failure = repository.failed[0]
    assert failure["error_code"] == "provider_5xx"
    assert failure["dead_lettered_at"] is None
    assert now + timedelta(seconds=30) <= failure["available_at"] <= now + timedelta(seconds=38)
    assert "raw-verification-token" not in repr(result)


def test_max_attempt_failure_moves_claim_to_dead_letter():
    now = datetime(2026, 7, 22, 16, tzinfo=UTC)
    claim = _claim(now=now, attempt_count=3)
    repository = FakeRepository([claim])

    result = asyncio.run(
        _dispatcher(
            repository,
            FakeProvider("provider_timeout"),
            now=now,
            max_attempts=3,
        ).dispatch_once()
    )

    assert result.dead_lettered == 1
    assert result.retry_scheduled == 0
    assert repository.failed[0]["dead_lettered_at"] == now


def test_ineligible_token_is_terminal_without_decryption_or_provider_call():
    now = datetime(2026, 7, 22, 16, tzinfo=UTC)
    claim = _claim(now=now, invalidated=now - timedelta(seconds=1))
    repository = FakeRepository([claim])
    provider = FakeProvider()

    result = asyncio.run(_dispatcher(repository, provider, now=now).dispatch_once())

    assert result.dead_lettered == 1
    assert provider.calls == []
    assert repository.failed[0]["error_code"] == "action_token_invalidated"


def test_stale_claim_owner_cannot_finalize_after_lease_reclaim():
    now = datetime(2026, 7, 22, 16, tzinfo=UTC)
    repository = FakeRepository([_claim(now=now)], finalize=False)

    result = asyncio.run(_dispatcher(repository, FakeProvider(), now=now).dispatch_once())

    assert result.delivered == 0
    assert result.stale_finalization == 1


@pytest.mark.parametrize(
    "value",
    (
        "http://provider.example.test/send",
        "https://user:secret@provider.example.test/send",
        "https://provider.example.test/send?debug=true",
        "https://provider.example.test/send#fragment",
    ),
)
def test_delivery_endpoints_require_clean_https_urls(value):
    with pytest.raises(ValueError):
        validate_https_endpoint(value, label="Provider")
