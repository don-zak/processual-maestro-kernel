from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from processual_api.integrations.provider_event_inbox import provider_event_chain_digest
from processual_api.integrations.provider_production_assurance import (
    CircuitState,
    ProviderHealth,
    ProviderObservation,
    ProviderPolicy,
    circuit_state_for_observation,
    classify_provider_health,
)

NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


def test_future_provider_observation_fails_closed() -> None:
    observation = ProviderObservation(
        provider_id="provider-future",
        observed_at=NOW + timedelta(seconds=1),
        success_rate=Decimal("1"),
        p95_latency_ms=1,
        consecutive_failures=0,
        evidence_reference="health:future",
    )
    policy = ProviderPolicy(observation_ttl_seconds=300)
    assert (
        classify_provider_health(observation, now=NOW, policy=policy)
        is ProviderHealth.UNKNOWN
    )
    assert (
        circuit_state_for_observation(observation, now=NOW, policy=policy)
        is CircuitState.OPEN
    )


def test_provider_event_genesis_digest_requires_hex_sha256() -> None:
    with pytest.raises(ValueError, match="genesis_digest"):
        provider_event_chain_digest([], genesis_digest="z" * 64)
