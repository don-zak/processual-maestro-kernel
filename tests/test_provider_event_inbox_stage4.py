from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from processual_api.integrations.provider_event_inbox import (
    PROVIDER_EVENT_CONSUMPTION_ENABLED,
    PROVIDER_EVENT_INBOX_STORAGE_ENABLED,
    ProviderInboxEvent,
    build_provider_event_inbox_status,
    canonical_payload_digest,
    provider_event_chain_digest,
    validate_provider_event_replay,
)

NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


def event(
    event_id: str,
    *,
    event_type: str = "provider.usage",
    payload: dict[str, object] | None = None,
) -> ProviderInboxEvent:
    body = payload or {"units": 10, "currency": "USD"}
    return ProviderInboxEvent(
        provider_id="provider-a",
        external_event_id=event_id,
        event_type=event_type,
        occurred_at=NOW,
        received_at=NOW + timedelta(seconds=1),
        payload_digest=canonical_payload_digest(body),
        evidence_reference=f"provider-evidence:{event_id}",
    )


def test_provider_event_idempotency_key_is_provider_scoped() -> None:
    item = event("evt-1")
    assert item.canonical_idempotency_key == "provider-event:provider-a:evt-1"


def test_exact_provider_event_replay_is_idempotent() -> None:
    existing = event("evt-1")
    incoming = event("evt-1")
    assert validate_provider_event_replay(existing, incoming) is existing


def test_conflicting_provider_event_replay_fails_closed() -> None:
    existing = event("evt-1", payload={"units": 10})
    incoming = event("evt-1", payload={"units": 11})
    with pytest.raises(ValueError, match="conflicts"):
        validate_provider_event_replay(existing, incoming)


def test_provider_event_chain_digest_is_order_sensitive() -> None:
    first = event("evt-1")
    second = event("evt-2")
    forward = provider_event_chain_digest([first, second])
    reverse = provider_event_chain_digest([second, first])
    assert len(forward) == 64
    assert forward != reverse


def test_provider_event_chain_detects_payload_tampering() -> None:
    original = [event("evt-1", payload={"units": 10}), event("evt-2")]
    tampered = [event("evt-1", payload={"units": 99}), event("evt-2")]
    assert provider_event_chain_digest(original) != provider_event_chain_digest(tampered)


def test_provider_event_timestamps_and_digest_are_strict() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ProviderInboxEvent(
            provider_id="provider-a",
            external_event_id="evt",
            event_type="usage",
            occurred_at=datetime(2026, 8, 10),
            received_at=NOW,
            payload_digest="a" * 64,
            evidence_reference="evidence",
        )
    with pytest.raises(ValueError, match="received_at"):
        ProviderInboxEvent(
            provider_id="provider-a",
            external_event_id="evt",
            event_type="usage",
            occurred_at=NOW,
            received_at=NOW - timedelta(seconds=1),
            payload_digest="a" * 64,
            evidence_reference="evidence",
        )
    with pytest.raises(ValueError, match="sha256"):
        ProviderInboxEvent(
            provider_id="provider-a",
            external_event_id="evt",
            event_type="usage",
            occurred_at=NOW,
            received_at=NOW,
            payload_digest="bad",
            evidence_reference="evidence",
        )


def test_provider_event_inbox_remains_disabled_by_default() -> None:
    status = build_provider_event_inbox_status()
    assert PROVIDER_EVENT_INBOX_STORAGE_ENABLED is False
    assert PROVIDER_EVENT_CONSUMPTION_ENABLED is False
    assert status["storage_enabled"] is False
    assert status["consumption_enabled"] is False
    assert status["unique_provider_external_event_required"] is True
    assert status["tamper_evident_chain_supported"] is True
