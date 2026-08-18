from __future__ import annotations

import pytest

from processual_api.integrations.endpoint_discovery_quality import (
    EndpointDiscoveryError,
    assess_endpoint_discovery,
)


def _camara_document() -> dict:
    return {
        "openapi": "3.0.3",
        "info": {"title": "CAMARA Test API", "version": "1.2.0"},
        "x-camara-commonalities": "0.6",
        "servers": [{"url": "https://sandbox.operator.example/camara/test/v1"}],
        "security": [{"oauth2": ["test:read"]}],
        "paths": {
            "/devices/{deviceId}/verify": {
                "parameters": [
                    {
                        "name": "deviceId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "post": {
                    "operationId": "verifyDevice",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    },
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {"application/json": {"schema": {"type": "object"}}},
                        }
                    },
                },
            }
        },
    }


def test_camara_release_contract_can_pass_discovery_quality() -> None:
    result = assess_endpoint_discovery(
        _camara_document(),
        contract_family="camara",
        source_reference="camaraproject/example@r3.2:code/API_definitions/example.yaml",
        release_pinned=True,
        external_references_resolved=True,
    )
    assert result["discovery_quality_passed"] is True
    assert result["binding_generation_ready"] is True
    assert result["operation_count"] == 1
    assert result["operations"][0]["operation_id"] == "verifyDevice"
    assert result["operations"][0]["security_scopes"] == ["test:read"]
    assert result["network_request_executed"] is False
    assert result["production_allowed"] is False


def test_camara_moving_or_wip_contract_is_blocked() -> None:
    document = _camara_document()
    document["info"]["version"] = "wip"
    result = assess_endpoint_discovery(
        document,
        contract_family="camara",
        source_reference="camaraproject/example@main:code/API_definitions/example.yaml",
        release_pinned=False,
        external_references_resolved=True,
    )
    assert result["discovery_quality_passed"] is False
    assert "immutable_release_source_required" in result["blocker_codes"]
    assert "camara_wip_version_not_qualifiable" in result["blocker_codes"]


def test_duplicate_or_missing_operation_ids_are_blocked() -> None:
    document = _camara_document()
    document["paths"]["/second"] = {
        "get": {
            "operationId": "verifyDevice",
            "responses": {"200": {"description": "OK"}},
        }
    }
    result = assess_endpoint_discovery(
        document,
        contract_family="generic_enterprise",
        source_reference="customer-api@v1.0.0:openapi.json",
        release_pinned=True,
        external_references_resolved=True,
    )
    assert "duplicate_operation_id" in result["blocker_codes"]

    del document["paths"]["/second"]["get"]["operationId"]
    result = assess_endpoint_discovery(
        document,
        contract_family="generic_enterprise",
        source_reference="customer-api@v1.0.0:openapi.json",
        release_pinned=True,
        external_references_resolved=True,
    )
    assert "operation_id_required" in result["blocker_codes"]


def test_invalid_path_parameter_contract_is_blocked() -> None:
    document = _camara_document()
    document["paths"]["/devices/{deviceId}/verify"]["parameters"][0]["required"] = False
    result = assess_endpoint_discovery(
        document,
        contract_family="camara",
        source_reference="camaraproject/example@r3.2:api.yaml",
        release_pinned=True,
        external_references_resolved=True,
    )
    assert "path_parameter_contract_invalid" in result["blocker_codes"]


def test_unresolved_external_refs_are_blocked() -> None:
    document = _camara_document()
    document["paths"]["/devices/{deviceId}/verify"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"] = {"$ref": "common.yaml#/components/schemas/Request"}
    result = assess_endpoint_discovery(
        document,
        contract_family="camara",
        source_reference="camaraproject/example@r3.2:api.yaml",
        release_pinned=True,
        external_references_resolved=False,
    )
    assert result["external_reference_count"] == 1
    assert "external_schema_references_must_be_resolved" in result["blocker_codes"]


def test_unsupported_description_dialect_is_rejected() -> None:
    with pytest.raises(EndpointDiscoveryError, match="unsupported_api_description_dialect"):
        assess_endpoint_discovery(
            {"openapi": "2.5", "info": {"title": "Bad", "version": "1"}, "paths": {}},
            contract_family="proprietary",
            source_reference="bad@v1:api.yaml",
            release_pinned=True,
            external_references_resolved=True,
        )
