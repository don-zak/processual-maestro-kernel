from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from processual_api.integrations.provider_production_assurance import (
    CircuitState,
    PRODUCTION_PROVIDER_EXECUTION_ENABLED,
    PRODUCTION_RELEASE_ENABLED,
    ProviderHealth,
    ProviderObservation,
    ProviderPolicy,
    ReleaseEvidence,
    ResilienceEvidence,
    RoutingCandidate,
    SloEvidence,
    build_release_assurance_status,
    choose_provider,
    circuit_state_for_observation,
    classify_provider_health,
    evidence_digest,
)

NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
POLICY = ProviderPolicy(
    minimum_success_rate=Decimal("0.99"),
    maximum_p95_latency_ms=3000,
    open_after_failures=5,
    observation_ttl_seconds=300,
)


def observation(
    provider_id: str = "provider-a",
    *,
    success_rate: str = "0.999",
    latency_ms: int = 1000,
    failures: int = 0,
    age_seconds: int = 0,
) -> ProviderObservation:
    return ProviderObservation(
        provider_id=provider_id,
        observed_at=NOW - timedelta(seconds=age_seconds),
        success_rate=Decimal(success_rate),
        p95_latency_ms=latency_ms,
        consecutive_failures=failures,
        evidence_reference=f"health:{provider_id}",
    )


def test_healthy_provider_closes_circuit() -> None:
    item = observation()
    assert classify_provider_health(item, now=NOW, policy=POLICY) is ProviderHealth.HEALTHY
    assert circuit_state_for_observation(item, now=NOW, policy=POLICY) is CircuitState.CLOSED


def test_low_success_rate_or_high_latency_degrades_provider() -> None:
    assert (
        classify_provider_health(
            observation(success_rate="0.95"), now=NOW, policy=POLICY
        )
        is ProviderHealth.DEGRADED
    )
    assert (
        classify_provider_health(
            observation(latency_ms=5000), now=NOW, policy=POLICY
        )
        is ProviderHealth.DEGRADED
    )


def test_failure_threshold_opens_circuit() -> None:
    item = observation(failures=5)
    assert classify_provider_health(item, now=NOW, policy=POLICY) is ProviderHealth.UNAVAILABLE
    assert circuit_state_for_observation(item, now=NOW, policy=POLICY) is CircuitState.OPEN


def test_stale_or_missing_observation_fails_closed() -> None:
    assert classify_provider_health(None, now=NOW, policy=POLICY) is ProviderHealth.UNKNOWN
    assert circuit_state_for_observation(None, now=NOW, policy=POLICY) is CircuitState.OPEN
    stale = observation(age_seconds=301)
    assert classify_provider_health(stale, now=NOW, policy=POLICY) is ProviderHealth.UNKNOWN


def test_degraded_provider_is_half_open_not_routable() -> None:
    item = observation(success_rate="0.98")
    assert circuit_state_for_observation(item, now=NOW, policy=POLICY) is CircuitState.HALF_OPEN
    decision = choose_provider(
        [RoutingCandidate("provider-a", 0, True, item)],
        now=NOW,
        policy=POLICY,
    )
    assert decision.selected_provider_id is None
    assert decision.reason == "no_approved_healthy_provider"


def test_routing_selects_highest_priority_approved_healthy_provider() -> None:
    decision = choose_provider(
        [
            RoutingCandidate("provider-b", 5, True, observation("provider-b")),
            RoutingCandidate("provider-a", 1, True, observation("provider-a")),
            RoutingCandidate("provider-c", 0, False, observation("provider-c")),
        ],
        now=NOW,
        policy=POLICY,
    )
    assert decision.selected_provider_id == "provider-a"
    assert decision.eligible_provider_ids == ("provider-a", "provider-b")
    assert decision.rejected_provider_ids == ("provider-c",)


def test_routing_never_uses_unknown_unapproved_or_open_provider() -> None:
    decision = choose_provider(
        [
            RoutingCandidate("missing", 0, True, None),
            RoutingCandidate("unapproved", 1, False, observation("unapproved")),
            RoutingCandidate("open", 2, True, observation("open", failures=9)),
        ],
        now=NOW,
        policy=POLICY,
    )
    assert decision.selected_provider_id is None
    assert decision.eligible_provider_ids == ()
    assert decision.rejected_provider_ids == ("missing", "open", "unapproved")


def test_resilience_requires_verified_backup_restore_and_rto_compliance() -> None:
    evidence = ResilienceEvidence(
        backup_verified_at=NOW,
        restore_verified_at=NOW,
        recovery_point_objective_minutes=15,
        recovery_time_objective_minutes=60,
        measured_restore_minutes=45,
    )
    assert evidence.ready is True
    late = ResilienceEvidence(
        backup_verified_at=NOW,
        restore_verified_at=NOW,
        recovery_point_objective_minutes=15,
        recovery_time_objective_minutes=60,
        measured_restore_minutes=61,
    )
    assert late.ready is False


def test_slo_requires_both_availability_and_latency_targets() -> None:
    good = SloEvidence(
        availability_target=Decimal("0.999"),
        measured_availability=Decimal("0.9995"),
        latency_target_ms=2000,
        measured_p95_latency_ms=1500,
    )
    assert good.met is True
    bad_latency = SloEvidence(
        availability_target=Decimal("0.999"),
        measured_availability=Decimal("0.9995"),
        latency_target_ms=2000,
        measured_p95_latency_ms=2500,
    )
    assert bad_latency.met is False


def release_evidence(*, ci: bool = True, security: bool = True) -> ReleaseEvidence:
    return ReleaseEvidence(
        release_id="release-2026-08-10",
        commit_sha="a" * 40,
        generated_at=NOW,
        ci_passed=ci,
        security_checks_passed=security,
        resilience=ResilienceEvidence(
            backup_verified_at=NOW,
            restore_verified_at=NOW,
            recovery_point_objective_minutes=15,
            recovery_time_objective_minutes=60,
            measured_restore_minutes=30,
        ),
        slo=SloEvidence(
            availability_target=Decimal("0.999"),
            measured_availability=Decimal("0.9999"),
            latency_target_ms=2000,
            measured_p95_latency_ms=1200,
        ),
        artifact_digest="b" * 64,
    )


def test_release_readiness_requires_ci_security_resilience_and_slo() -> None:
    assert release_evidence().production_ready is True
    assert release_evidence(ci=False).production_ready is False
    assert release_evidence(security=False).production_ready is False


def test_release_status_never_enables_production_capability() -> None:
    status = build_release_assurance_status(release_evidence())
    assert status["production_ready"] is True
    assert status["production_provider_execution_enabled"] is False
    assert status["production_release_enabled"] is False
    assert PRODUCTION_PROVIDER_EXECUTION_ENABLED is False
    assert PRODUCTION_RELEASE_ENABLED is False


def test_evidence_digest_is_deterministic_and_sensitive_to_changes() -> None:
    one = evidence_digest({"b": 2, "a": 1})
    two = evidence_digest({"a": 1, "b": 2})
    changed = evidence_digest({"a": 1, "b": 3})
    assert one == two
    assert one != changed
    assert len(one) == 64


def test_release_status_has_separate_evidence_and_artifact_digests() -> None:
    status = build_release_assurance_status(release_evidence())
    assert len(str(status["evidence_digest"])) == 64
    assert status["artifact_digest"] == "b" * 64
    assert status["evidence_digest"] != status["artifact_digest"]


def test_invalid_observations_and_release_digests_fail_closed() -> None:
    with pytest.raises(ValueError, match="success_rate"):
        observation(success_rate="1.1")
    with pytest.raises(ValueError, match="timezone-aware"):
        ProviderObservation(
            provider_id="x",
            observed_at=datetime(2026, 8, 10),
            success_rate=Decimal("1"),
            p95_latency_ms=1,
            consecutive_failures=0,
            evidence_reference="evidence:x",
        )
    with pytest.raises(ValueError, match="sha256"):
        ReleaseEvidence(
            release_id="r",
            commit_sha="a" * 40,
            generated_at=NOW,
            ci_passed=True,
            security_checks_passed=True,
            resilience=release_evidence().resilience,
            slo=release_evidence().slo,
            artifact_digest="not-a-digest",
        )
