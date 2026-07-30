from datetime import UTC, datetime

import pytest

from processual_api.billing.commercial_provider_evidence_contracts import (
    ProviderChannel,
    ProviderEventEnvelope,
    ProviderEvidenceState,
    build_provider_evidence_status,
    decide_provider_evidence,
    digest_payload,
    digest_signature,
    verify_digest,
)

NOW = datetime(2026, 7, 30, 17, 10, tzinfo=UTC)


def test_digest_helpers_do_not_expose_raw_payload_or_signature() -> None:
    payload = b'{"event":"payment_success"}'
    signature = "provider-secret-signature"

    payload_digest = digest_payload(payload)
    signature_digest = digest_signature(signature)

    assert len(payload_digest) == 64
    assert len(signature_digest) == 64
    assert payload.decode() not in payload_digest
    assert signature not in signature_digest
    assert verify_digest(
        expected_digest=payload_digest,
        observed_digest=payload_digest,
    )


def test_valid_provider_event_is_evidence_only() -> None:
    decision = decide_provider_evidence(
        signature_valid=True,
        replay_detected=False,
    )

    assert decision.state is ProviderEvidenceState.SIGNATURE_VERIFIED
    assert decision.accepted_as_evidence is True
    assert decision.grant_allowed is False
    assert decision.runtime_write_allowed is False


@pytest.mark.parametrize(
    ("signature_valid", "replay", "state"),
    (
        (
            False,
            False,
            ProviderEvidenceState.INVALID_SIGNATURE,
        ),
        (
            True,
            True,
            ProviderEvidenceState.REPLAY_REJECTED,
        ),
    ),
)
def test_invalid_or_replayed_event_is_rejected(
    signature_valid,
    replay,
    state,
) -> None:
    decision = decide_provider_evidence(
        signature_valid=signature_valid,
        replay_detected=replay,
    )

    assert decision.state is state
    assert decision.accepted_as_evidence is False
    assert decision.grant_allowed is False


def test_event_envelope_contains_digests_only() -> None:
    envelope = ProviderEventEnvelope(
        provider_channel=ProviderChannel.LEMON_SQUEEZY,
        provider_event_reference="event:1",
        provider_payment_reference="payment:1",
        occurred_at=NOW,
        received_at=NOW,
        payload_digest=digest_payload(b"safe"),
        signature_digest=digest_signature("signature"),
        replay_key="replay:event:1",
    )

    payload = envelope.to_safe_dict()
    assert payload["payload_digest"]
    assert payload["signature_digest"]


def test_provider_runtime_remains_disabled() -> None:
    status = build_provider_evidence_status()

    assert status["webhook_runtime_enabled"] is False
    assert status["event_writes_enabled"] is False
    assert status["direct_grant_allowed"] is False
    assert status["secret_logging_allowed"] is False
