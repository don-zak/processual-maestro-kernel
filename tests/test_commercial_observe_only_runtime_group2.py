from datetime import UTC, datetime

import pytest

from processual_api.billing.commercial_observe_only_runtime import (
    CommercialObservation,
    CommercialObservationKind,
    build_commercial_observe_only_status,
    evaluate_observation,
)

NOW = datetime(2026, 7, 30, 17, 10, tzinfo=UTC)


def observation(
    kind: CommercialObservationKind,
) -> CommercialObservation:
    return CommercialObservation(
        kind=kind,
        tenant_reference="tenant:1",
        subscription_reference="subscription:1",
        correlation_reference="correlation:1",
        observed_at=NOW,
        state="observed",
        metric_value=10,
    )


def test_observation_never_enforces_or_mutates() -> None:
    decision = evaluate_observation(observation(CommercialObservationKind.ENTITLEMENT_BALANCE))

    assert decision.recorded is False
    assert decision.enforcement_applied is False
    assert decision.state_mutated is False


def test_reconciliation_mismatch_requests_notification_only() -> None:
    decision = evaluate_observation(observation(CommercialObservationKind.RECONCILIATION_MISMATCH))

    assert decision.notification_required is True
    assert decision.enforcement_applied is False
    assert decision.state_mutated is False


def test_sensitive_payload_is_rejected() -> None:
    with pytest.raises(ValueError, match="sensitive payloads"):
        CommercialObservation(
            kind=CommercialObservationKind.PAYMENT_EVIDENCE,
            tenant_reference="tenant:1",
            subscription_reference="subscription:1",
            correlation_reference="correlation:1",
            observed_at=NOW,
            state="observed",
            metric_value=None,
            sensitive_payload_included=True,
        )


def test_observe_only_flags_remain_disabled() -> None:
    status = build_commercial_observe_only_status()

    assert status["enabled"] is False
    assert status["runtime_writes_enabled"] is False
    assert status["quota_enforcement_enabled"] is False
    assert status["load_shedding_enabled"] is False
    assert status["automatic_activation_enabled"] is False
    assert status["ledger_mutation_allowed"] is False
    assert status["reconciliation_auto_repair_allowed"] is False
