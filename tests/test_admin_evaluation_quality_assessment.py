from __future__ import annotations

import asyncio

from processual_api.integrations.api_key_access_policy import list_api_key_access_policies
from processual_api.routers import settings_admin_evaluation_coverage as coverage_route
from processual_api.services import usage_log_store
from processual_api.services.evaluation_quality_assessment import (
    assess_evaluation_campaign_quality,
)


PUBLIC_PROBES = {
    ("GET", "/health/live"),
    ("GET", "/health/ready"),
}


def _configure(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(usage_log_store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(usage_log_store, "_USAGE_LOG_PATH", tmp_path / "usage_logs.jsonl")


def _append(method: str, path: str, *, status: int = 200, latency: float = 10.0) -> None:
    usage_log_store.append_usage_log(
        {
            "client_id": "quality-campaign",
            "api_key_id": "evalkey-quality",
            "auth_method": "api_key",
            "method": method,
            "endpoint": path,
            "status_code": status,
            "latency_ms": latency,
            "entitlement_source": "admin_evaluation_grant",
            "evaluation_grant_id": "eval-quality",
            "execution_mode": "evaluation_runtime",
            "real_runtime_execution": True,
            "production_allowed": False,
        }
    )


def _protected():
    return [
        policy
        for policy in list_api_key_access_policies()
        if (policy.method, policy.path) not in PUBLIC_PROBES
    ]


def test_quality_gate_requires_repeatable_success_on_every_protected_endpoint(
    monkeypatch,
    tmp_path,
) -> None:
    _configure(monkeypatch, tmp_path)
    for policy in _protected():
        for latency in (10.0, 12.0, 15.0):
            _append(policy.method, policy.path, latency=latency)

    result = assess_evaluation_campaign_quality(client_id="quality-campaign")

    assert result["protected_runtime_coverage_complete"] is True
    assert result["repeatability_evidence_complete"] is True
    assert result["quality_gate_passed"] is True
    assert result["quality_evidence_percent"] == 100.0
    assert result["thresholds"]["min_successes_per_endpoint"] == 3
    assert result["thresholds"]["max_failure_rate"] == 0.0
    assert result["public_probe_evidence_required"] is True
    assert result["cross_application_evidence_required"] is True
    for row in result["endpoints"]:
        assert row["success_count"] == 3
        assert row["failure_count"] == 0
        assert row["p50_latency_ms"] == 12.0
        assert row["p95_latency_ms"] == 15.0
        assert row["quality_evidence_sufficient"] is True


def test_one_failed_attempt_blocks_zero_failure_quality_gate(monkeypatch, tmp_path) -> None:
    _configure(monkeypatch, tmp_path)
    policies = _protected()
    for policy in policies:
        for _ in range(3):
            _append(policy.method, policy.path)
    failing = policies[0]
    _append(failing.method, failing.path, status=500, latency=20.0)

    result = assess_evaluation_campaign_quality(client_id="quality-campaign")
    row = next(item for item in result["endpoints"] if item["path"] == failing.path)

    assert row["failure_count"] == 1
    assert row["failure_rate"] == 0.25
    assert row["failure_rate_ok"] is False
    assert result["quality_gate_passed"] is False


def test_explicit_p95_limit_blocks_slow_endpoint(monkeypatch, tmp_path) -> None:
    _configure(monkeypatch, tmp_path)
    policies = _protected()
    for policy in policies:
        for latency in (10.0, 11.0, 12.0):
            _append(policy.method, policy.path, latency=latency)
    slow = policies[-1]
    for latency in (200.0, 250.0, 300.0):
        _append(slow.method, slow.path, latency=latency)

    result = assess_evaluation_campaign_quality(
        client_id="quality-campaign",
        min_successes_per_endpoint=3,
        max_failure_rate=0.0,
        max_p95_latency_ms=100.0,
    )
    row = next(item for item in result["endpoints"] if item["path"] == slow.path)

    assert row["p95_latency_ms"] == 300.0
    assert row["latency_ok"] is False
    assert result["quality_gate_passed"] is False


def test_quality_status_route_is_super_admin_only(monkeypatch, tmp_path) -> None:
    _configure(monkeypatch, tmp_path)
    observed: list[dict] = []

    async def _authority(current_user: dict) -> None:
        observed.append(current_user)

    monkeypatch.setattr(coverage_route, "require_active_platform_admin", _authority)
    user = {"sub": "platform-owner", "session_type": "identity_user"}

    result = asyncio.run(
        coverage_route.evaluation_quality_status(
            client_id="quality-campaign",
            min_successes_per_endpoint=3,
            max_failure_rate=0.0,
            max_p95_latency_ms=None,
            current_user=user,
        )
    )

    assert observed == [user]
    assert result["client_id"] == "quality-campaign"
    assert result["raw_secret_visible"] is False
