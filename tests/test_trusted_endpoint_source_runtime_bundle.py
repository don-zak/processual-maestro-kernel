from __future__ import annotations

import pytest
from fastapi import HTTPException

from processual_api.integrations.endpoint_discovery_quality import (
    canonical_api_description_sha256,
)
from processual_api.integrations.endpoint_source_attestation import TrustedEndpointSourceRecord
from processual_api.integrations.enterprise_endpoint_bindings import BINDING_STORAGE_KEY
from processual_api.integrations.trusted_endpoint_source_acquisition import (
    AcquiredTrustedEndpointSource,
)
from processual_api.routers import settings_endpoint_discovery_qualification_runtime as runtime

COMMIT = "0123456789abcdef0123456789abcdef01234567"


def _binding() -> dict:
    return {
        "binding_id": "binding.crm.customer_context",
        "display_name": "Customer context",
        "adapter_contract_id": "crm",
        "task_id": "crm.customer_context",
        "credential_profile_id": "enterprise_core_api_reference",
        "environment": "sandbox",
        "base_url": "https://sandbox.customer.example/api",
        "method": "GET",
        "path": "/customers/{customer_id}",
        "required_scope_ids": ["crm:read"],
        "path_parameters": {"customer_id": "$task.customer_id"},
        "query_parameters": {},
        "request_headers": {},
        "response_format": "json",
        "response_data_path": "$",
        "field_mapping": {"customer_id": "$.id"},
        "success_codes": [200],
        "timeout_seconds": 15,
    }


def _document() -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Customer API", "version": "1.4.2"},
        "servers": [{"url": "https://sandbox.customer.example/api/v1"}],
        "paths": {
            "/customers/{customer_id}": {
                "get": {
                    "operationId": "getCustomerContext",
                    "parameters": [
                        {
                            "name": "customer_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Customer context",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "../common/customer.yaml#/Customer"}
                                }
                            },
                        }
                    },
                }
            }
        },
    }


def _acquired(*, resolved: bool) -> AcquiredTrustedEndpointSource:
    document = _document()
    path = "openapi/releases/v1/openapi.yaml"
    reference = f"github:standards/customer-api@{COMMIT}:{path}"
    record = TrustedEndpointSourceRecord(
        source_identity_id="standards.customer-api",
        contract_family="generic_enterprise",
        source_reference=reference,
        source_kind="git_commit",
        source_revision=COMMIT,
        source_sha256=canonical_api_description_sha256(document),
        policy_version="reviewed-catalog-r1",
    )
    return AcquiredTrustedEndpointSource(
        api_description=document,
        trusted_record=record,
        repository="standards/customer-api",
        path=path,
        external_references_resolved=resolved,
        source_bundle_sha256="b" * 64 if resolved else "",
        source_bundle_paths=(
            path,
            "openapi/common/customer.yaml",
        ) if resolved else (path,),
    )


@pytest.mark.asyncio
async def test_trusted_route_uses_acquisition_bundle_resolution_and_returns_safe_manifest(
    monkeypatch,
) -> None:
    raw = {BINDING_STORAGE_KEY: [_binding()]}
    monkeypatch.setattr(runtime, "_require_enterprise", lambda _user: ("client-1", raw))
    monkeypatch.setattr(runtime.settings_module, "_save_raw", lambda _user, _raw: None)

    async def fake_acquire(**_kwargs):
        return _acquired(resolved=True)

    monkeypatch.setattr(runtime, "acquire_trusted_github_endpoint_source", fake_acquire)
    body = runtime.TrustedEndpointDiscoveryQualificationRequest(
        source_identity_id="standards.customer-api",
        source_revision=COMMIT,
        source_path="openapi/releases/v1/openapi.yaml",
        operation_id="getCustomerContext",
    )

    result = await runtime.qualify_endpoint_binding_from_trusted_source(
        "binding.crm.customer_context",
        body,
        current_user={"sub": "client-1"},
    )

    assert result["assessment"]["external_reference_count"] == 1
    assert result["assessment"]["external_references_resolved"] is True
    assert result["assessment"]["discovery_quality_passed"] is True
    assert result["trusted_source_bundle_sha256"] == "b" * 64
    assert result["trusted_source_bundle_paths"] == [
        "openapi/releases/v1/openapi.yaml",
        "openapi/common/customer.yaml",
    ]
    stored = raw[runtime.DISCOVERY_PROVENANCE_STORAGE_KEY][0]
    assert "api_description" not in stored
    assert "source_bundle_paths" not in stored


@pytest.mark.asyncio
async def test_trusted_route_stays_fail_closed_when_acquisition_did_not_resolve_refs(
    monkeypatch,
) -> None:
    raw = {BINDING_STORAGE_KEY: [_binding()]}
    monkeypatch.setattr(runtime, "_require_enterprise", lambda _user: ("client-1", raw))
    monkeypatch.setattr(
        runtime.settings_module,
        "_save_raw",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not persist")),
    )

    async def fake_acquire(**_kwargs):
        return _acquired(resolved=False)

    monkeypatch.setattr(runtime, "acquire_trusted_github_endpoint_source", fake_acquire)
    body = runtime.TrustedEndpointDiscoveryQualificationRequest(
        source_identity_id="standards.customer-api",
        source_revision=COMMIT,
        source_path="openapi/releases/v1/openapi.yaml",
        operation_id="getCustomerContext",
    )

    with pytest.raises(HTTPException) as exc:
        await runtime.qualify_endpoint_binding_from_trusted_source(
            "binding.crm.customer_context",
            body,
            current_user={"sub": "client-1"},
        )

    assert exc.value.status_code == 422
    assert "discovery_quality_must_pass" in str(exc.value.detail)
    assert runtime.DISCOVERY_PROVENANCE_STORAGE_KEY not in raw
