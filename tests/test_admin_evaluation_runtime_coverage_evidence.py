from __future__ import annotations

import asyncio

from processual_api.integrations.api_key_access_policy import (
    list_api_key_access_policies,
)
from processual_api.middleware.usage_log import _evaluation_usage_record
from processual_api.routers import settings_admin_evaluation_coverage as coverage_route
from processual_api.services import usage_log_store


PUBLIC_PROBES = {
    ("GET", "/health/live"),
    ("GET", "/health/ready"),
}


def _configure_log_path(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(usage_log_store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(
        usage_log_store,
        "_USAGE_LOG_PATH",
        tmp_path / "usage_logs.jsonl",
    )


def _append_success(
    method: str,
    path: str,
    *,
    grant_id: str,
    key_id: str,
) -> None:
    usage_log_store.append_usage_log(
        {
            "client_id": "evaluation-campaign-client",
            "user_id": "evaluation-user",
            "api_key_id": key_id,
            "api_key_prefix": "pmk_example...",
            "auth_method": "api_key",
            "session_type": "api_key",
            "method": method,
            "endpoint": path,
            "status_code": 200,
            "latency_ms": 12.5,
            "role": "client",
            "entitlement_source": "admin_evaluation_grant",
            "evaluation_grant_id": grant_id,
            "execution_mode": "evaluation_runtime",
            "real_runtime_execution": True,
            "endpoint_authority_source": "canonical_runtime_access_policy",
            "task_authority_source": "integration_task_catalog",
            "evaluation_request_limit": 100,
            "evaluation_request_used": 1,
            "evaluation_request_remaining": 99,
            "production_allowed": False,
        }
    )


def test_evaluation_usage_metadata_is_emitted_without_raw_secret() -> None:
    record = _evaluation_usage_record(
        {
            "entitlement_source": "admin_evaluation_grant",
            "evaluation_grant_id": "eval-1",
            "execution_mode": "evaluation_runtime",
            "real_runtime_execution": True,
            "endpoint_authority_source": "canonical_runtime_access_policy",
            "task_authority_source": "integration_task_catalog",
            "evaluation_request_limit": 10,
            "evaluation_request_used": 3,
            "evaluation_request_remaining": 7,
            "production_allowed": False,
            "raw_api_key": "pmk_must_never_be_logged",
        }
    )

    assert record["evaluation_grant_id"] == "eval-1"
    assert record["execution_mode"] == "evaluation_runtime"
    assert record["real_runtime_execution"] is True
    assert record["production_allowed"] is False
    assert "raw_api_key" not in record


def test_campaign_coverage_aggregates_multiple_bounded_grants_by_client_id(
    monkeypatch,
    tmp_path,
) -> None:
    _configure_log_path(monkeypatch, tmp_path)
    protected = [
        policy
        for policy in list_api_key_access_policies()
        if (policy.method, policy.path) not in PUBLIC_PROBES
    ]

    for index, policy in enumerate(protected[:-1]):
        _append_success(
            policy.method,
            policy.path,
            grant_id=f"eval-campaign-{index % 3}",
            key_id=f"evalkey-campaign-{index % 3}",
        )

    summary = usage_log_store.summarize_evaluation_endpoint_coverage(
        client_id="evaluation-campaign-client",
    )

    assert summary["campaign_correlation"] == "client_id"
    assert summary["protected_endpoint_count"] == len(protected)
    assert summary["protected_endpoint_success_count"] == len(protected) - 1
    assert summary["protected_runtime_coverage_complete"] is False
    assert summary["protected_coverage_percent"] < 100

    missing = protected[-1]
    _append_success(
        missing.method,
        missing.path,
        grant_id="eval-campaign-2",
        key_id="evalkey-campaign-2",
    )
    complete = usage_log_store.summarize_evaluation_endpoint_coverage(
        client_id="evaluation-campaign-client",
    )

    assert complete["protected_endpoint_success_count"] == len(protected)
    assert complete["protected_coverage_percent"] == 100.0
    assert complete["protected_runtime_coverage_complete"] is True
    assert complete["public_probe_count"] == 2
    assert complete["full_campaign_requires_public_probe_evidence"] is True


def test_failed_runtime_attempt_does_not_count_as_endpoint_success(
    monkeypatch,
    tmp_path,
) -> None:
    _configure_log_path(monkeypatch, tmp_path)
    policy = next(
        policy
        for policy in list_api_key_access_policies()
        if policy.path == "/cgt/govern"
    )
    usage_log_store.append_usage_log(
        {
            "client_id": "evaluation-campaign-client",
            "api_key_id": "evalkey-coverage",
            "auth_method": "api_key",
            "method": policy.method,
            "endpoint": policy.path,
            "status_code": 500,
            "latency_ms": 25,
            "entitlement_source": "admin_evaluation_grant",
            "evaluation_grant_id": "eval-coverage",
            "execution_mode": "evaluation_runtime",
            "real_runtime_execution": True,
            "production_allowed": False,
        }
    )

    summary = usage_log_store.summarize_evaluation_endpoint_coverage(
        client_id="evaluation-campaign-client",
    )
    row = next(
        endpoint
        for endpoint in summary["endpoints"]
        if endpoint["path"] == policy.path
    )
    assert row["attempt_count"] == 1
    assert row["success_count"] == 0
    assert row["failure_count"] == 1
    assert row["observed_success"] is False


def test_coverage_status_route_remains_super_admin_only(monkeypatch, tmp_path) -> None:
    _configure_log_path(monkeypatch, tmp_path)
    observed: list[dict] = []

    async def _authority(current_user: dict) -> None:
        observed.append(current_user)

    monkeypatch.setattr(
        coverage_route,
        "require_active_platform_admin",
        _authority,
    )
    current_user = {"sub": "platform-owner", "session_type": "identity_user"}

    result = asyncio.run(
        coverage_route.evaluation_coverage_status(
            client_id=None,
            evaluation_grant_id=None,
            api_key_id=None,
            current_user=current_user,
        )
    )

    assert observed == [current_user]
    assert result["policy_endpoint_count"] == len(list_api_key_access_policies())
    assert result["raw_secret_visible"] is False
