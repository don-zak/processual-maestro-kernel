from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from processual_api.billing.maestro_execution_authority import (
    APPROVED_FOR_CHECKOUT,
    APPROVED_FOR_INVOICING,
    APPROVED_FOR_QUOTA,
    APPROVED_FOR_SETTLEMENT,
    DISCOVERY_ONLY,
    RUNTIME_INSTRUMENTATION_ENABLED,
    MaestroExecutionAttemptContext,
    MaestroExecutionAuthorityKind,
    MaestroExecutionAuthorityValidationError,
    MaestroExecutionCompletion,
    MaestroExecutionCompletionStatus,
    NoOpMaestroExecutionObserver,
)


def make_context(**overrides):
    values = {
        "execution_id": "execution-001",
        "attempt_id": "attempt-001",
        "authority_kind": (MaestroExecutionAuthorityKind.LLM_ADAPTER),
        "started_at": datetime(2026, 7, 28, tzinfo=UTC),
    }
    values.update(overrides)
    return MaestroExecutionAttemptContext(**values)


def test_r2b_remains_discovery_only():
    assert DISCOVERY_ONLY is True
    assert RUNTIME_INSTRUMENTATION_ENABLED is False
    assert APPROVED_FOR_QUOTA is False
    assert APPROVED_FOR_INVOICING is False
    assert APPROVED_FOR_CHECKOUT is False
    assert APPROVED_FOR_SETTLEMENT is False


def test_attempt_context_is_frozen():
    context = make_context()

    with pytest.raises(FrozenInstanceError):
        context.execution_id = "changed"  # type: ignore[misc]


def test_retry_requires_idempotency_key():
    with pytest.raises(MaestroExecutionAuthorityValidationError):
        make_context(retry_ordinal=1)


def test_retry_accepts_stable_idempotency_key():
    context = make_context(
        retry_ordinal=1,
        idempotency_key="execution-001",
    )

    assert context.retry_ordinal == 1
    assert context.idempotency_key == "execution-001"


def test_completion_requires_monotonic_utc_time():
    context = make_context()

    with pytest.raises(MaestroExecutionAuthorityValidationError):
        MaestroExecutionCompletion(
            context=context,
            completed_at=(context.started_at - timedelta(seconds=1)),
            status=MaestroExecutionCompletionStatus.COMPLETED,
        )


def test_failed_completion_requires_failure_code():
    with pytest.raises(MaestroExecutionAuthorityValidationError):
        MaestroExecutionCompletion(
            context=make_context(),
            completed_at=datetime(2026, 7, 28, tzinfo=UTC),
            status=MaestroExecutionCompletionStatus.FAILED,
        )


def test_noop_observer_never_changes_execution():
    observer = NoOpMaestroExecutionObserver()
    context = make_context()
    completion = MaestroExecutionCompletion(
        context=context,
        completed_at=context.started_at,
        status=MaestroExecutionCompletionStatus.COMPLETED,
    )

    assert observer.attempt_started(context) is None
    assert observer.attempt_completed(completion) is None


def test_llm_connection_policy_is_byok_only() -> None:
    from processual_api.billing import maestro_execution_authority as authority

    assert authority.LLM_CONNECTION_POLICY == "byok_only"
    assert authority.PLATFORM_OWNED_LLM_KEYS_ALLOWED is False
    assert authority.LLM_CREDENTIALS_REQUIRED_FOR_LIVE_CALLS is True


def test_llm_sensitive_content_is_forbidden_in_measurements() -> None:
    from processual_api.billing import maestro_execution_authority as authority

    assert authority.LLM_CREDENTIALS_ALLOWED_IN_MEASUREMENTS is False
    assert authority.LLM_RAW_PROMPTS_ALLOWED_IN_MEASUREMENTS is False
    assert authority.LLM_RAW_RESPONSES_ALLOWED_IN_MEASUREMENTS is False
