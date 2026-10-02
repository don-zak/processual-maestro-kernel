from __future__ import annotations

import asyncio
import inspect
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from processual_api.routers import settings_admin_evaluation_grants as grant_routes
from processual_api.routers import settings_admin_evaluation_quota_policy as quota_routes
from processual_api.services.evaluation_key_quota_policy import (
    CRM_EVALUATION_KEY_QUOTA,
    EVALUATION_KEY_TYPE_CRM,
    EVALUATION_KEY_TYPE_INTEGRATION,
    INTEGRATION_EVALUATION_KEY_QUOTA,
    INTEGRATION_EVALUATION_KEY_QUOTA_MULTIPLIER,
    evaluation_key_quota,
    normalized_evaluation_key_type,
)


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/settings/admin/evaluation-grants",
            "raw_path": b"/settings/admin/evaluation-grants",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
            "root_path": "",
        }
    )


def _body(**overrides):
    values = {
        "client_id": "external-evaluator",
        "issued_to": "External Evaluator",
        "purpose": "Governed external evaluation quota policy test",
        "allowed_task_ids": ["crm.customer_context"],
        "allowed_binding_ids": [],
        "allowed_endpoints": [{"method": "GET", "path": "/health/live"}],
        "allowed_scopes": ["read:health"],
        "max_requests": 4999,
        "expires_in_days": 14,
    }
    values.update(overrides)
    return quota_routes.QuotaGovernedEvaluationGrantCreate(**values)


async def _selectable_catalog(*, request, current_user):
    del request, current_user
    return {
        "bindings": [
            {
                "binding_id": "binding_1",
                "task_id": "crm.customer_context",
                "selectable": True,
                "sandbox_readiness": {"sandbox_ready": True},
            }
        ]
    }


def test_integration_quota_is_derived_as_exactly_twice_crm() -> None:
    assert CRM_EVALUATION_KEY_QUOTA == 100
    assert INTEGRATION_EVALUATION_KEY_QUOTA_MULTIPLIER == 2
    assert INTEGRATION_EVALUATION_KEY_QUOTA == CRM_EVALUATION_KEY_QUOTA * 2
    assert evaluation_key_quota(EVALUATION_KEY_TYPE_CRM) == CRM_EVALUATION_KEY_QUOTA
    assert evaluation_key_quota(EVALUATION_KEY_TYPE_INTEGRATION) == INTEGRATION_EVALUATION_KEY_QUOTA


def test_standard_alias_fails_safe_to_crm_baseline() -> None:
    assert normalized_evaluation_key_type("standard") == EVALUATION_KEY_TYPE_CRM
    assert evaluation_key_quota("standard") == CRM_EVALUATION_KEY_QUOTA


def test_explicit_grant_type_is_authoritative_over_runtime_shape() -> None:
    task_execute = [
        SimpleNamespace(method="POST", path="/evaluation/runtime/task-execute")
    ]

    assert (
        normalized_evaluation_key_type(
            "crm",
            allowed_binding_ids=["binding_1"],
            allowed_endpoints=task_execute,
        )
        == EVALUATION_KEY_TYPE_CRM
    )
    assert (
        normalized_evaluation_key_type(
            "integration",
            allowed_binding_ids=[],
            allowed_endpoints=[],
        )
        == EVALUATION_KEY_TYPE_INTEGRATION
    )


def test_legacy_payload_without_type_can_infer_integration_runtime() -> None:
    assert (
        normalized_evaluation_key_type(None, allowed_binding_ids=["binding_1"])
        == EVALUATION_KEY_TYPE_INTEGRATION
    )
    assert (
        normalized_evaluation_key_type(
            None,
            allowed_endpoints=[
                SimpleNamespace(method="POST", path="/evaluation/runtime/task-execute")
            ],
        )
        == EVALUATION_KEY_TYPE_INTEGRATION
    )


def test_quota_governed_route_ignores_client_quota_and_passes_type_to_canonical_write(
    monkeypatch,
) -> None:
    captured: list[tuple[str | None, int]] = []

    async def fake_create(*, body, request, current_user):
        del request, current_user
        captured.append((body.evaluation_type, body.max_requests))
        return {
            "status": "created",
            "grant": {
                "grant_id": "eval_test",
                "evaluation_type": body.evaluation_type,
                "max_requests": body.max_requests,
                "quota_unit": "admitted_execution",
                "quota_policy": "integration_equals_2x_crm",
            },
        }

    monkeypatch.setattr(quota_routes, "create_evaluation_grant", fake_create)
    monkeypatch.setattr(quota_routes, "evaluation_binding_catalog", _selectable_catalog)

    crm = asyncio.run(
        quota_routes.create_quota_governed_evaluation_grant(
            body=_body(
                evaluation_type="crm",
                max_requests=4999,
                allowed_binding_ids=["binding_1"],
                allowed_endpoints=[
                    {"method": "POST", "path": "/evaluation/runtime/task-execute"}
                ],
            ),
            request=_request(),
            current_user={"sub": "admin"},
        )
    )
    assert captured[-1] == (EVALUATION_KEY_TYPE_CRM, CRM_EVALUATION_KEY_QUOTA)
    assert crm["grant"]["max_requests"] == CRM_EVALUATION_KEY_QUOTA
    assert crm["grant"]["evaluation_type"] == EVALUATION_KEY_TYPE_CRM
    assert crm["grant"]["quota_unit"] == "admitted_execution"
    assert crm["grant"]["quota_policy"] == "integration_equals_2x_crm"

    integration = asyncio.run(
        quota_routes.create_quota_governed_evaluation_grant(
            body=_body(
                evaluation_type="integration",
                max_requests=1,
                allowed_binding_ids=["binding_1"],
            ),
            request=_request(),
            current_user={"sub": "admin"},
        )
    )
    assert captured[-1] == (
        EVALUATION_KEY_TYPE_INTEGRATION,
        INTEGRATION_EVALUATION_KEY_QUOTA,
    )
    assert integration["grant"]["max_requests"] == CRM_EVALUATION_KEY_QUOTA * 2
    assert integration["grant"]["evaluation_type"] == EVALUATION_KEY_TYPE_INTEGRATION


def test_runtime_grant_rejects_binding_that_is_not_sandbox_ready(monkeypatch) -> None:
    called = False

    async def blocked_catalog(*, request, current_user):
        del request, current_user
        return {
            "bindings": [
                {
                    "binding_id": "binding_1",
                    "task_id": "crm.customer_context",
                    "selectable": False,
                    "sandbox_readiness": {
                        "sandbox_ready": False,
                        "blocker_codes": ["hardened_live_sandbox_proof_required"],
                    },
                }
            ]
        }

    async def fake_create(*, body, request, current_user):
        nonlocal called
        del body, request, current_user
        called = True
        return {"status": "created", "grant": {}}

    monkeypatch.setattr(quota_routes, "evaluation_binding_catalog", blocked_catalog)
    monkeypatch.setattr(quota_routes, "create_evaluation_grant", fake_create)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            quota_routes.create_quota_governed_evaluation_grant(
                body=_body(
                    evaluation_type="crm",
                    allowed_binding_ids=["binding_1"],
                    allowed_endpoints=[
                        {
                            "method": "POST",
                            "path": "/evaluation/runtime/task-execute",
                        }
                    ],
                ),
                request=_request(),
                current_user={"sub": "admin"},
            )
        )

    assert exc_info.value.status_code == 422
    assert "sandbox-ready" in str(exc_info.value.detail)
    assert called is False


def test_runtime_grant_rejects_selectable_binding_outside_task_envelope(monkeypatch) -> None:
    async def wrong_task_catalog(*, request, current_user):
        del request, current_user
        return {
            "bindings": [
                {
                    "binding_id": "binding_1",
                    "task_id": "billing.account_context",
                    "selectable": True,
                }
            ]
        }

    monkeypatch.setattr(quota_routes, "evaluation_binding_catalog", wrong_task_catalog)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            quota_routes.create_quota_governed_evaluation_grant(
                body=_body(
                    evaluation_type="crm",
                    allowed_binding_ids=["binding_1"],
                    allowed_endpoints=[
                        {
                            "method": "POST",
                            "path": "/evaluation/runtime/task-execute",
                        }
                    ],
                ),
                request=_request(),
                current_user={"sub": "admin"},
            )
        )

    assert exc_info.value.status_code == 422
    assert "outside the grant task envelope" in str(exc_info.value.detail)


def test_quota_wrapper_has_no_secondary_authority_load_or_save() -> None:
    source = inspect.getsource(quota_routes.create_quota_governed_evaluation_grant)
    assert "load_evaluation_authority_state" not in source
    assert "save_evaluation_authority_state" not in source
    assert "evaluation_type=resolved_type" in source


def test_canonical_grant_creation_seals_quota_metadata_before_single_save() -> None:
    source = inspect.getsource(grant_routes.create_evaluation_grant)
    assert source.count("save_evaluation_authority_state(") == 1
    assert '"evaluation_type": evaluation_type' in source
    assert '"quota_unit": "admitted_execution" if evaluation_type else ""' in source
    assert '"quota_policy": "integration_equals_2x_crm" if evaluation_type else ""' in source
    assert source.index('"evaluation_type": evaluation_type') < source.index(
        "save_evaluation_authority_state("
    )
