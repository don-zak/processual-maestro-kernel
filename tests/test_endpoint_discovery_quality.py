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
        "components": {
            "securitySchemes": {
                "oauth2": {
                    "type": "oauth2",
                    "flows": {
                        "clientCredentials": {
                            "tokenUrl": "https://auth.operator.example/oauth/token",
                            "scopes": {"test:read": "Read test capability"},
                        }
                    },
                }
            }
        },
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
    assert result["operations"][0]["security_schemes"] == ["oauth2"]
    assert result["operations"][0]["security_scopes"] == ["test:read"]
    assert result["defined_security_schemes"] == ["oauth2"]
    assert result["undefined_security_schemes"] == []
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


def test_undefined_security_scheme_is_blocked() -> None:
    document = _camara_document()
    document["security"] = [{"missingOAuth": ["test:read"]}]
    result = assess_endpoint_discovery(
        document,
        contract_family="camara",
        source_reference="camaraproject/example@r3.2:api.yaml",
        release_pinned=True,
        external_references_resolved=True,
    )

    assert result["discovery_quality_passed"] is False
    assert result["undefined_security_schemes"] == ["missingOAuth"]
    assert "security_scheme_definition_required" in result["blocker_codes"]


def test_swagger_2_inherits_root_consumes_produces_and_security_definitions() -> None:
    document = {
        "swagger": "2.0",
        "info": {"title": "TM Forum-style Test API", "version": "5.0.0"},
        "basePath": "/tmf-api/serviceQualification/v5",
        "consumes": ["application/json"],
        "produces": ["application/json"],
        "securityDefinitions": {
            "oauth2": {
                "type": "oauth2",
                "flow": "application",
                "tokenUrl": "https://auth.operator.example/oauth/token",
                "scopes": {"service:write": "Write service qualification"},
            }
        },
        "security": [{"oauth2": ["service:write"]}],
        "paths": {
            "/checkServiceQualification": {
                "post": {
                    "operationId": "checkServiceQualification",
                    "parameters": [
                        {
                            "name": "body",
                            "in": "body",
                            "required": True,
                            "schema": {"type": "object"},
                        }
                    ],
                    "responses": {"201": {"description": "Created"}},
                }
            }
        },
    }

    result = assess_endpoint_discovery(
        document,
        contract_family="tm_forum",
        source_reference="tmforum-api@v5.0.0:TMF645-ServiceQualification-v5.0.0.swagger.json",
        release_pinned=True,
        external_references_resolved=True,
    )

    operation = result["operations"][0]
    assert result["discovery_quality_passed"] is True
    assert operation["request_media_types"] == ["application/json"]
    assert operation["response_media_types"] == ["application/json"]
    assert operation["security_schemes"] == ["oauth2"]
    assert operation["security_scopes"] == ["service:write"]
    assert not any(
        warning.startswith("request_media_type_not_declared")
        for warning in result["warning_codes"]
    )


def test_swagger_operation_media_types_override_root_defaults() -> None:
    document = {
        "swagger": "2.0",
        "info": {"title": "Override Test", "version": "1.0.0"},
        "consumes": ["application/json"],
        "produces": ["application/json"],
        "paths": {
            "/objects": {
                "post": {
                    "operationId": "createObject",
                    "consumes": ["application/merge-patch+json"],
                    "produces": ["application/problem+json"],
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }

    result = assess_endpoint_discovery(
        document,
        contract_family="generic_enterprise",
        source_reference="provider@v1.0.0:swagger.json",
        release_pinned=True,
        external_references_resolved=True,
    )

    operation = result["operations"][0]
    assert operation["request_media_types"] == ["application/merge-patch+json"]
    assert operation["response_media_types"] == ["application/problem+json"]


def test_unsupported_description_dialect_is_rejected() -> None:
    with pytest.raises(EndpointDiscoveryError, match="unsupported_api_description_dialect"):
        assess_endpoint_discovery(
            {"openapi": "2.5", "info": {"title": "Bad", "version": "1"}, "paths": {}},
            contract_family="proprietary",
            source_reference="bad@v1:api.yaml",
            release_pinned=True,
            external_references_resolved=True,
        )
