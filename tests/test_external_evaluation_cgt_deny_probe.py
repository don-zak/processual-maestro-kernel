from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from processual_api.routers import evaluation_cgt_probe as probe
from processual_api.services.evaluation_grants import (
    EVALUATION_CGT_DENY_PROBE_ENDPOINT,
    evaluation_endpoint_allowed,
)


def _credential() -> dict:
    return {
        "auth_method": "api_key",
        "entitlement_source": "admin_evaluation_grant",
        "evaluation_grant_id": "eval_probe",
        "api_key_id": "evalkey_probe",
        "client_id": "probe-client",
        "allowed_endpoints": [
            {"method": "POST", "path": "/evaluation/runtime/task-execute"}
        ],
        "allowed_task_ids": ["crm.customer_context"],
        "allowed_binding_ids": ["evaluation.crm.customer_context.owned"],
        "scopes": ["run:evaluation"],
        "quota_limit": 100,
    }


def test_deny_probe_is_intrinsic_but_not_added_to_grant_authority() -> None:
    identity = _credential()
    assert EVALUATION_CGT_DENY_PROBE_ENDPOINT == (
        "POST",
        "/evaluation/runtime/governance-deny-probe",
    )
    assert evaluation_endpoint_allowed(
        identity,
        method="POST",
        path="/evaluation/runtime/governance-deny-probe",
    )
    assert all(
        item.get("path") != "/evaluation/runtime/governance-deny-probe"
        for item in identity["allowed_endpoints"]
    )


def test_deny_probe_persists_safe_evidence_before_403(monkeypatch) -> None:
    identity = _credential()

    async def load(owner_id: str) -> dict:
        assert owner_id
        return {"evaluation_grants_v1": []}

    def require(current_user: dict, raw: dict) -> None:
        assert current_user is identity
        assert isinstance(raw, dict)

    persisted: dict = {}

    async def persist(**kwargs):
        persisted.update(kwargs)
        return {
            "governance_evidence_persisted": True,
            "quota_consumed": False,
            "network_request_executed": False,
        }

    monkeypatch.setattr(probe, "load_evaluation_authority_state", load)
    monkeypatch.setattr(probe, "_require_evaluation_credential", require)
    monkeypatch.setattr(probe, "persist_evaluation_cgt_denial", persist)

    body = probe.EvaluationCGTDenyProbeRequest(
        probe_id="CGT-DENY-01",
        idempotency_key="deny-probe-test-0001",
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            probe.run_evaluation_cgt_deny_probe(
                body=body,
                current_user=identity,
            )
        )

    assert exc.value.status_code == 403
    detail = exc.value.detail
    assert detail["code"] == "evaluation_cgt_governance_denied"
    assert detail["probe_id"] == "CGT-DENY-01"
    assert detail["probe_kind"] == "governance_only_non_executable"
    assert detail["disposition"] == "deny"
    assert detail["governance_action"] == "reject"
    assert detail["governance_evidence_persisted"] is True
    assert detail["quota_consumed"] is False
    assert detail["network_request_executed"] is False
    assert detail["production_allowed"] is False
    assert detail["authority_expansion_allowed"] is False
    assert detail["raw_task_input_persisted"] is False
    assert detail["raw_secret_visible"] is False
    assert persisted["task_id"] == probe.CGT_DENY_PROBE_TASK_ID
    assert persisted["binding_id"] == probe.CGT_DENY_PROBE_BINDING_ID
    assert persisted["governance"]["disposition"] == "deny"


def test_deny_probe_route_is_registered() -> None:
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "processual_api"
        / "routers"
        / "external_evaluation_route_registry.py"
    ).read_text(encoding="utf-8")
    assert "run_evaluation_cgt_deny_probe" in source
    assert '"/evaluation/runtime/governance-deny-probe"' in source
