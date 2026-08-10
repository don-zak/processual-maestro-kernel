from __future__ import annotations

from datetime import UTC, datetime

from processual_api.services.enterprise_endpoint_failure_review import (
    FAILURE_STORAGE_KEY,
    classify_sandbox_failure,
    list_safe_sandbox_failures,
    mark_failure_reviewing,
    record_sandbox_failure,
    resolve_failures_after_success,
)


def test_failure_taxonomy_is_closed_and_actionable() -> None:
    credential = classify_sandbox_failure(
        ValueError("sandbox_credential_reference_unresolved")
    )
    assert credential == {
        "stage": "credential",
        "failure_code": "credential_unavailable",
        "recommended_action": (
            "Verify the deployment credential reference and its sandbox scope."
        ),
        "retryable": True,
    }

    blocked = classify_sandbox_failure(
        ValueError("sandbox_destination_not_public")
    )
    assert blocked["stage"] == "destination"
    assert blocked["failure_code"] == "destination_blocked"
    assert blocked["retryable"] is False


def test_record_never_persists_raw_exception_or_secret_material() -> None:
    raw: dict = {}
    record = record_sandbox_failure(
        raw,
        binding_id="billing.account",
        task_id="billing.account_context",
        exc=ValueError("Bearer super-secret-token sandbox_http_request_failed"),
        now=datetime(2026, 8, 10, 18, 0, tzinfo=UTC),
    )
    assert record["failure_code"] == "transport_failed"
    assert record["raw_error_included"] is False
    assert record["raw_secret_visible"] is False
    serialized = repr(raw[FAILURE_STORAGE_KEY]).lower()
    assert "super-secret-token" not in serialized
    assert "bearer " not in serialized


def test_attempts_review_and_successful_retest_form_audit_lifecycle() -> None:
    raw: dict = {}
    first = record_sandbox_failure(
        raw,
        binding_id="crm.customer",
        task_id="crm.customer_context",
        exc=ValueError("sandbox_destination_dns_failed"),
        now=datetime(2026, 8, 10, 18, 0, tzinfo=UTC),
    )
    second = record_sandbox_failure(
        raw,
        binding_id="crm.customer",
        task_id="crm.customer_context",
        exc=ValueError("sandbox_http_request_failed"),
        now=datetime(2026, 8, 10, 18, 1, tzinfo=UTC),
    )
    assert first["attempt"] == 1
    assert second["attempt"] == 2

    reviewing = mark_failure_reviewing(
        raw,
        failure_id=first["failure_id"],
        now=datetime(2026, 8, 10, 18, 2, tzinfo=UTC),
    )
    assert reviewing["status"] == "reviewing"

    resolved = resolve_failures_after_success(
        raw,
        binding_id="crm.customer",
        task_id="crm.customer_context",
        evidence_sha256="e" * 64,
        now=datetime(2026, 8, 10, 18, 3, tzinfo=UTC),
    )
    assert resolved == 2
    failures = list_safe_sandbox_failures(raw)
    assert {item["status"] for item in failures} == {"resolved"}
    assert {item["resolution_code"] for item in failures} == {
        "successful_sandbox_retest"
    }
    assert {item["evidence_sha256"] for item in failures} == {"e" * 64}
