from __future__ import annotations

from processual_api.integrations.camara_qod_external_sandbox_qualification import (
    TELEFONICA_QOD_EXTERNAL_SANDBOX_EVIDENCE,
    camara_qod_external_sandbox_qualification_payload,
)
from processual_api.integrations.camara_qod_telefonica_compatibility import (
    camara_qod_telefonica_compatibility_payload,
)


def test_telefonica_external_evidence_is_independent_and_non_authoritative() -> None:
    evidence = TELEFONICA_QOD_EXTERNAL_SANDBOX_EVIDENCE
    assert evidence.provider == "telefonica_open_gateway"
    assert evidence.provider_api_version == "v0.10"
    assert evidence.authorization_flow == "CIBA"
    assert evidence.proven_operations == (
        "createSession",
        "getSession",
        "deleteSession",
        "extendQosSessionDuration",
    )
    assert evidence.authenticated_sandbox_reachability_proven is True
    assert evidence.external_mock_sandbox_proven is True
    assert evidence.external_mock_extend_proven is True
    assert evidence.negative_path_conformance_complete is False
    assert evidence.missing_session_documented_expectation_met is False
    assert evidence.mock_documentation_divergence_observed is True
    assert evidence.operator_network_qos_proven is False
    assert evidence.governed_camara_v1_1_provider_sandbox_proven is False
    assert evidence.runtime_connector_approved is False
    assert evidence.production_allowed is False


def test_external_qualification_payload_does_not_upgrade_provider_gate() -> None:
    payload = camara_qod_external_sandbox_qualification_payload()
    assert payload["evidence_class"] == "external_mock_interoperability_with_divergence"
    assert payload["compatible_with_governed_contract"] == "partial_semantic_only"
    assert payload["provider_sandbox_proven"] is False
    assert payload["runtime_connector_approved"] is False
    assert payload["production_allowed"] is False
    assert "telefonica_api_version_differs_from_governed_camara_v1_1" in payload[
        "qualification_blockers"
    ]
    assert "telefonica_missing_session_returns_200_instead_of_documented_404" in payload[
        "qualification_blockers"
    ]
    assert "telefonica_negative_path_conformance_incomplete" in payload[
        "qualification_blockers"
    ]
    assert "retrieve_sessions_by_device_unproven" in payload["qualification_blockers"]


def test_telefonica_compatibility_is_partial_and_fail_closed() -> None:
    payload = camara_qod_telefonica_compatibility_payload()
    assert payload["provider_api_version"] == "v0.10"
    assert payload["governed_api_version"] == "1.1.0"
    assert (
        payload["compatibility_state"]
        == "partial_interoperability_with_negative_path_divergence"
    )
    assert payload["provider_proven_operation_ids"] == [
        "createSession",
        "getSession",
        "deleteSession",
        "extendQosSessionDuration",
    ]
    assert payload["semantically_matching_operation_ids"] == [
        "createSession",
        "getSession",
        "deleteSession",
        "extendQosSessionDuration",
    ]
    assert payload["negative_path_conformance_complete"] is False
    assert payload["missing_session_documented_expectation_met"] is False
    assert payload["mock_documentation_divergence_observed"] is True
    assert payload["provider_sandbox_proven"] is False
    assert payload["runtime_connector_approved"] is False
    assert payload["production_allowed"] is False
    assert "telefonica_missing_session_returns_200_instead_of_documented_404" in payload[
        "blocker_codes"
    ]
    assert "telefonica_negative_path_conformance_incomplete" in payload["blocker_codes"]
    assert "telefonica_retrieve_sessions_by_device_unproven" in payload[
        "blocker_codes"
    ]
