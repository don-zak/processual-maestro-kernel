from __future__ import annotations

import pytest

from processual_api.integrations.adapter_contracts import get_adapter_contract
from processual_api.integrations.camara_qod_semantic_mapping import (
    APPROVAL_GATED_WRITE,
    CAMARA_QOD_R32_CALLBACK_OPERATION_IDS,
    CAMARA_QOD_R32_CALLABLE_OPERATION_IDS,
    READ,
    assess_camara_qod_semantic_alignment,
    camara_qod_semantic_mapping_payload,
    get_camara_qod_semantic_mapping,
)
from processual_api.integrations.integration_task_catalog import (
    SUPPORTED_INTEGRATION_TASKS,
)
from processual_api.integrations.trusted_endpoint_source_acquisition import (
    CAMARA_QOD_R32_COMMIT,
    CAMARA_QOD_R32_PATH,
)


def _discovered_operations() -> list[dict[str, object]]:
    return [
        {
            "operation_id": operation_id,
            "method": get_camara_qod_semantic_mapping(operation_id).method,
            "path": get_camara_qod_semantic_mapping(operation_id).path,
            "security_scopes": [
                get_camara_qod_semantic_mapping(operation_id).camara_scope
            ],
        }
        for operation_id in CAMARA_QOD_R32_CALLABLE_OPERATION_IDS
    ]


def test_qod_r32_callable_operations_and_scopes_are_exact() -> None:
    assert CAMARA_QOD_R32_CALLABLE_OPERATION_IDS == (
        "createSession",
        "getSession",
        "deleteSession",
        "extendQosSessionDuration",
        "retrieveSessionsByDevice",
    )
    expected = {
        "createSession": ("POST", "/sessions", "quality-on-demand:sessions:create"),
        "getSession": (
            "GET",
            "/sessions/{sessionId}",
            "quality-on-demand:sessions:read",
        ),
        "deleteSession": (
            "DELETE",
            "/sessions/{sessionId}",
            "quality-on-demand:sessions:delete",
        ),
        "extendQosSessionDuration": (
            "POST",
            "/sessions/{sessionId}/extend",
            "quality-on-demand:sessions:update",
        ),
        "retrieveSessionsByDevice": (
            "POST",
            "/retrieve-sessions",
            "quality-on-demand:sessions:retrieve-by-device",
        ),
    }
    for operation_id, contract in expected.items():
        mapping = get_camara_qod_semantic_mapping(operation_id)
        assert (mapping.method, mapping.path, mapping.camara_scope) == contract


def test_qod_write_semantics_are_not_downgraded_to_network_assurance_reads() -> None:
    network = get_adapter_contract("network_assurance")
    assert network.optional_write_scopes == ()
    assert "network:write" in network.restricted_scopes

    assert get_camara_qod_semantic_mapping("getSession").operation_class == READ
    assert (
        get_camara_qod_semantic_mapping("retrieveSessionsByDevice").operation_class
        == READ
    )
    for operation_id in ("createSession", "deleteSession", "extendQosSessionDuration"):
        mapping = get_camara_qod_semantic_mapping(operation_id)
        assert mapping.operation_class == APPROVAL_GATED_WRITE
        assert mapping.proposed_task_id not in SUPPORTED_INTEGRATION_TASKS
        assert mapping.runtime_task_registered is False
        assert mapping.runtime_connector_approved is False
        assert mapping.production_allowed is False


def test_create_session_contract_captures_required_and_conditional_identity_inputs() -> None:
    mapping = get_camara_qod_semantic_mapping("createSession")
    assert mapping.required_input_fields == (
        "application_server",
        "qos_profile",
        "duration_seconds",
    )
    assert "device" in mapping.optional_input_fields
    assert "two_legged_token_requires_device" in mapping.conditional_input_rules
    assert "three_legged_token_forbids_device" in mapping.conditional_input_rules
    assert (
        "notification_sink_credential_must_be_managed_reference"
        in mapping.conditional_input_rules
    )
    assert "device_identifier_possible_personal_data" in mapping.data_classifications


def test_retrieve_by_device_records_post_as_read_and_conditional_subject_resolution() -> None:
    mapping = get_camara_qod_semantic_mapping("retrieveSessionsByDevice")
    assert mapping.method == "POST"
    assert mapping.operation_class == READ
    assert mapping.required_input_fields == ()
    assert mapping.optional_input_fields == ("device",)
    assert set(mapping.conditional_input_rules) == {
        "two_legged_token_requires_device",
        "three_legged_token_forbids_device",
        "three_legged_token_subject_selects_device",
    }


def test_callback_is_explicitly_excluded_from_outbound_binding() -> None:
    assert CAMARA_QOD_R32_CALLBACK_OPERATION_IDS == ("postNotification",)
    with pytest.raises(KeyError, match="Unsupported CAMARA QoD operation"):
        get_camara_qod_semantic_mapping("postNotification")


def test_semantic_alignment_accepts_only_exact_reviewed_inventory() -> None:
    result = assess_camara_qod_semantic_alignment(_discovered_operations())
    assert result["semantic_mapping_aligned"] is True
    assert result["semantic_mapping_blocker_codes"] == []
    assert result["aligned_operation_ids"] == list(CAMARA_QOD_R32_CALLABLE_OPERATION_IDS)
    assert result["runtime_task_registered"] is False
    assert result["runtime_connector_approved"] is False
    assert result["production_allowed"] is False


@pytest.mark.parametrize(
    "mutation,expected_blocker",
    [
        ({"method": "PUT"}, "camara_qod_method_drift:createSession"),
        ({"path": "/v2/sessions"}, "camara_qod_path_drift:createSession"),
        (
            {"security_scopes": ["quality-on-demand:sessions:read"]},
            "camara_qod_scope_drift:createSession",
        ),
    ],
)
def test_semantic_alignment_rejects_method_path_or_scope_drift(
    mutation: dict[str, object],
    expected_blocker: str,
) -> None:
    operations = _discovered_operations()
    operations[0] = {**operations[0], **mutation}
    result = assess_camara_qod_semantic_alignment(operations)
    assert result["semantic_mapping_aligned"] is False
    assert expected_blocker in result["semantic_mapping_blocker_codes"]


def test_semantic_alignment_rejects_missing_and_unreviewed_operations() -> None:
    operations = _discovered_operations()[1:]
    operations.append(
        {
            "operation_id": "futureUnreviewedOperation",
            "method": "POST",
            "path": "/future",
            "security_scopes": ["quality-on-demand:future"],
        }
    )
    result = assess_camara_qod_semantic_alignment(operations)
    assert result["semantic_mapping_aligned"] is False
    assert result["semantic_mapping_blocker_codes"] == [
        "camara_qod_expected_operation_missing:createSession",
        "camara_qod_unreviewed_operation_present:futureUnreviewedOperation",
    ]


def test_semantic_mapping_payload_is_pinned_proposal_only_and_non_authoritative() -> None:
    payload = camara_qod_semantic_mapping_payload()
    assert payload["source_identity_id"] == "camara.quality_on_demand.r3_2"
    assert payload["source_revision"] == CAMARA_QOD_R32_COMMIT
    assert payload["source_path"] == CAMARA_QOD_R32_PATH
    assert payload["api_version"] == "1.1.0"
    assert payload["mapping_state"] == "proposal_only"
    assert payload["existing_network_assurance_reused"] is False
    assert payload["runtime_task_registered"] is False
    assert payload["runtime_connector_approved"] is False
    assert payload["provider_sandbox_proven"] is False
    assert payload["production_allowed"] is False
    assert len(payload["callable_operations"]) == 5
    assert payload["callback_operations_excluded_from_outbound_binding"] == [
        "postNotification"
    ]
