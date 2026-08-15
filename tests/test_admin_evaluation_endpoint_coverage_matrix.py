from __future__ import annotations

import pytest

from processual_api.integrations.api_key_access_policy import (
    list_api_key_access_policies,
)
from processual_api.services.evaluation_grants import evaluation_endpoint_allowed


# This is a release-readiness contract, not a claim that every row has already
# passed against a deployed external program. CI requires every grantable
# endpoint to have a declared proof objective and authorization envelope. Real
# external-run evidence is collected separately before the PR can leave Draft.
ENDPOINT_EVALUATION_MATRIX: dict[tuple[str, str], dict[str, object]] = {
    ("GET", "/health/live"): {
        "coverage_class": "public_availability_probe",
        "task_id": "platform.health.live",
        "success_proof": "service process is alive and responds with the expected runtime identity",
        "failure_proof": "unavailable process or malformed liveness response is observable",
        "api_key_authorization_proof": False,
        "external_repeatability_required": True,
    },
    ("GET", "/health/ready"): {
        "coverage_class": "public_availability_probe",
        "task_id": "platform.health.ready",
        "success_proof": "declared runtime dependencies report readiness coherently",
        "failure_proof": "dependency unavailability is surfaced without false-ready status",
        "api_key_authorization_proof": False,
        "external_repeatability_required": True,
    },
    ("GET", "/adapters/status"): {
        "coverage_class": "evaluation_protected_observability",
        "task_id": "platform.adapters.status",
        "success_proof": "adapter/provider inventory and configuration state are returned through the issued key",
        "failure_proof": "unselected endpoint and revoked/expired key fail closed",
        "api_key_authorization_proof": True,
        "external_repeatability_required": True,
    },
    ("GET", "/cgt/govern/status"): {
        "coverage_class": "evaluation_protected_observability",
        "task_id": "platform.governor.status",
        "success_proof": "governor state, providers, and evaluation count are observable through the issued key",
        "failure_proof": "unselected endpoint and invalid key fail before handler authority",
        "api_key_authorization_proof": True,
        "external_repeatability_required": True,
    },
    ("POST", "/cgt/analyze"): {
        "coverage_class": "evaluation_protected_execution",
        "task_id": "platform.cgt.analyze",
        "success_proof": "representative input produces a structurally valid CGT analysis result",
        "failure_proof": "invalid input and unauthorized endpoint selection fail predictably",
        "api_key_authorization_proof": True,
        "external_repeatability_required": True,
    },
    ("POST", "/cgt/govern"): {
        "coverage_class": "evaluation_protected_execution",
        "task_id": "platform.cgt.govern",
        "success_proof": "governance evaluation produces signed decision data and observable evaluation evidence",
        "failure_proof": "invalid input, quota exhaustion, revoke, and unauthorized selection fail closed",
        "api_key_authorization_proof": True,
        "external_repeatability_required": True,
    },
    ("GET", "/cgt/govern/reports"): {
        "coverage_class": "evaluation_protected_observability",
        "task_id": "platform.governor.reports",
        "success_proof": "evaluation reports reflect recorded governed executions without exposing secrets",
        "failure_proof": "unauthorized endpoint selection and invalid credential fail closed",
        "api_key_authorization_proof": True,
        "external_repeatability_required": True,
    },
    ("POST", "/evaluation/runtime/task-execute"): {
        "coverage_class": "evaluation_protected_real_task_execution",
        "task_id": "platform.evaluation.task_execute",
        "success_proof": "allowed canonical task executes the prepared real external operation and records task-level evidence",
        "failure_proof": "task mismatch, ungranted task, missing preparation, revoked/expired/quota-exhausted key, and unsafe peer fail closed",
        "api_key_authorization_proof": True,
        "external_repeatability_required": True,
    },
}


def _evaluation_identity_for(policy) -> dict[str, object]:
    return {
        "auth_method": "api_key",
        "entitlement_source": "admin_evaluation_grant",
        "execution_mode": "evaluation_runtime",
        "real_runtime_execution": True,
        "allowed_endpoints": [
            {
                "method": policy.method,
                "path": policy.path,
            }
        ],
    }


def test_every_grantable_endpoint_has_exactly_one_evaluation_scenario() -> None:
    policies = list_api_key_access_policies()
    policy_keys = {(policy.method, policy.path) for policy in policies}

    assert set(ENDPOINT_EVALUATION_MATRIX) == policy_keys
    assert len(ENDPOINT_EVALUATION_MATRIX) == len(policies)

    policies_by_key = {(policy.method, policy.path): policy for policy in policies}
    for key, scenario in ENDPOINT_EVALUATION_MATRIX.items():
        policy = policies_by_key[key]
        assert scenario["task_id"] == policy.task_id
        assert str(scenario["success_proof"]).strip()
        assert str(scenario["failure_proof"]).strip()
        assert scenario["external_repeatability_required"] is True


def test_only_public_health_probes_are_not_api_key_authorization_proofs() -> None:
    public = {
        key
        for key, scenario in ENDPOINT_EVALUATION_MATRIX.items()
        if scenario["api_key_authorization_proof"] is False
    }
    assert public == {
        ("GET", "/health/live"),
        ("GET", "/health/ready"),
    }


@pytest.mark.parametrize(
    "method,path",
    [
        key
        for key, scenario in ENDPOINT_EVALUATION_MATRIX.items()
        if scenario["api_key_authorization_proof"] is True
    ],
)
def test_each_protected_endpoint_is_allowed_only_when_explicitly_selected(
    method: str,
    path: str,
) -> None:
    policies = {
        (policy.method, policy.path): policy
        for policy in list_api_key_access_policies()
    }
    selected = policies[(method, path)]
    identity = _evaluation_identity_for(selected)

    assert evaluation_endpoint_allowed(identity, method, path) is True

    for other in policies.values():
        other_key = (other.method, other.path)
        if other_key == (method, path):
            continue
        assert evaluation_endpoint_allowed(
            identity,
            other.method,
            other.path,
        ) is False


def test_control_plane_is_never_part_of_endpoint_evaluation_matrix() -> None:
    for method, path in ENDPOINT_EVALUATION_MATRIX:
        assert method in {"GET", "POST", "PUT", "PATCH", "DELETE"}
        assert not path.startswith(("/settings", "/admin", "/auth"))
