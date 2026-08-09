from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from processual_api.integrations.adapter_contracts import get_adapter_contract
from processual_api.integrations.credential_profiles import (
    COMMON_REQUIRED_CUSTOMER_INPUTS,
    get_credential_profile,
)
from processual_api.routers import settings as settings_router
from processual_api.routers import settings_enterprise_integration_runtime as enterprise_runtime
from processual_api.routers.settings_enterprise_integration_runtime import (
    EnterpriseSandboxQualificationRequest,
    enterprise_integration_console_payload,
    evaluate_enterprise_sandbox_qualification,
)


def _client(plan_id: str = "enterprise_integration") -> dict:
    return {
        "sub": "client-a",
        "user_id": "client-a",
        "client_id": "client-a",
        "role": "client",
        "plan_id": plan_id,
    }


def _profile_scope_id(
    profile_id: str = "enterprise_core_api_reference",
) -> str:
    profile = get_credential_profile(profile_id)
    for contract_id in profile.adapter_contract_ids:
        contract = get_adapter_contract(contract_id)
        if contract.required_scopes:
            return contract.required_scopes[0]
    raise AssertionError(f"Profile {profile_id} has no required adapter scope")


def test_enterprise_integration_console_route_is_registered() -> None:
    paths = {
        route.path
        for route in settings_router.router.routes
        if isinstance(route, APIRoute)
    }

    assert "/settings/enterprise-integration" in paths
    assert "/settings/enterprise-integration/sandbox-qualification" in paths


def test_locked_plan_returns_upgrade_only_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        settings_router,
        "_load_raw",
        lambda user_id: {
            "subscription": {"plan_id": "starter"},
            "api_keys": [
                {
                    "id": "hidden-key",
                    "client_id": "client-a",
                    "status": "enabled",
                    "hashed": "never-return-this",
                }
            ],
        },
    )

    payload = enterprise_integration_console_payload(
        current_user=_client("starter")
    )

    assert payload["enabled"] is False
    assert payload["status"] == "locked"
    assert payload["key_count"] == 0
    assert payload["keys"] == []
    assert payload["readiness_checks"] == []
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False
    assert payload["raw_secret_visible"] is False
    assert payload["scope_posture"] == {
        "enabled": False,
        "source": "catalog",
        "total": 0,
        "read": 0,
        "write": 0,
        "restricted": 0,
        "read_only_pilot": 0,
        "supervisor_approval_required": 0,
        "production_allowed_without_approval": 0,
    }
    assert payload["sections"] == [
        {
            "id": "entitlement",
            "label": "Enterprise entitlement",
            "status": "locked",
            "next_action": "Upgrade to an eligible Enterprise Integration plan.",
        }
    ]


def test_enterprise_console_returns_safe_key_and_readiness_metadata(monkeypatch) -> None:
    monkeypatch.setattr(
        settings_router,
        "_load_raw",
        lambda user_id: {
            "subscription": {"plan_id": "enterprise_integration"},
            "api_keys": [
                {
                    "id": "key-a",
                    "prefix": "pmk_safe...",
                    "client_id": "client-a",
                    "status": "enabled",
                    "scopes": ["read:health"],
                    "hashed": "never-return-this",
                    "api_key": "never-return-this-either",
                },
                {
                    "id": "other-client-key",
                    "prefix": "pmk_other...",
                    "client_id": "client-b",
                    "status": "enabled",
                },
            ],
        },
    )

    payload = enterprise_integration_console_payload(
        current_user=_client("enterprise_integration")
    )

    assert payload["enabled"] is True
    assert payload["status"] == "available"
    assert payload["environment"] == "sandbox"
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False
    assert payload["raw_secret_visible"] is False
    assert payload["key_count"] == 1
    assert payload["keys"][0]["key_id"] == "key-a"
    assert payload["keys"][0]["client_id"] == "client-a"
    assert "hashed" not in payload["keys"][0]
    assert "api_key" not in payload["keys"][0]
    assert payload["operational_profile_count"] >= 1
    assert payload["scope_posture"]["enabled"] is True
    assert payload["scope_posture"]["source"] == "catalog"
    assert payload["scope_posture"]["total"] >= 1
    assert payload["scope_posture"]["read"] >= 1
    assert payload["scope_posture"]["write"] >= 1
    assert payload["scope_posture"]["restricted"] >= 1
    assert payload["scope_posture"]["read_only_pilot"] >= 1
    assert payload["scope_posture"]["supervisor_approval_required"] >= 1
    assert payload["scope_posture"]["production_allowed_without_approval"] == 0
    assert payload["readiness"]["total"] >= 1
    assert payload["readiness"]["production_allowed"] == 0
    assert payload["readiness"]["runtime_connector_approved"] == 0
    assert all(
        check["production_allowed"] is False
        for check in payload["readiness_checks"]
    )
    assert all(
        check["runtime_connector_approved"] is False
        for check in payload["readiness_checks"]
    )
    assert [section["id"] for section in payload["sections"]] == [
        "entitlement",
        "api_keys",
        "integration_profile",
        "readiness",
        "production",
    ]


def test_scope_posture_counts_are_internally_consistent(monkeypatch) -> None:
    monkeypatch.setattr(
        settings_router,
        "_load_raw",
        lambda user_id: {
            "subscription": {"plan_id": "enterprise_core"},
            "api_keys": [],
        },
    )

    payload = enterprise_integration_console_payload(
        current_user=_client("enterprise_core")
    )
    posture = payload["scope_posture"]

    assert posture["source"] == "catalog"
    assert posture["total"] == posture["read"] + posture["write"] + posture["restricted"]
    assert posture["read_only_pilot"] == posture["read"]
    assert posture["supervisor_approval_required"] == (
        posture["write"] + posture["restricted"]
    )
    assert posture["production_allowed_without_approval"] == 0


def test_enterprise_console_evaluates_readiness_once(monkeypatch) -> None:
    monkeypatch.setattr(
        settings_router,
        "_load_raw",
        lambda user_id: {
            "subscription": {"plan_id": "enterprise_core"},
            "api_keys": [],
        },
    )
    original = enterprise_runtime.list_integration_readiness_checks
    calls = 0

    def counted_readiness_checks():
        nonlocal calls
        calls += 1
        return original()

    monkeypatch.setattr(
        enterprise_runtime,
        "list_integration_readiness_checks",
        counted_readiness_checks,
    )

    payload = enterprise_integration_console_payload(
        current_user=_client("enterprise_core")
    )

    assert calls == 1
    assert payload["readiness"]["total"] == len(payload["readiness_checks"])


def test_enterprise_private_remains_legacy_compatible(monkeypatch) -> None:
    monkeypatch.setattr(
        settings_router,
        "_load_raw",
        lambda user_id: {
            "subscription": {"plan_id": "enterprise_private"},
            "api_keys": [],
        },
    )

    payload = enterprise_integration_console_payload(
        current_user=_client("enterprise_private")
    )

    assert payload["enabled"] is True
    assert payload["legacy_compatibility"] is True
    assert payload["plan_id"] == "enterprise_private"


def test_endpoint_payload_has_no_secret_markers(monkeypatch) -> None:
    monkeypatch.setattr(
        settings_router,
        "_load_raw",
        lambda user_id: {
            "subscription": {"plan_id": "enterprise_core"},
            "api_keys": [],
        },
    )

    payload = asyncio.run(
        __import__(
            "processual_api.routers.settings_enterprise_integration_runtime",
            fromlist=["get_enterprise_integration_console"],
        ).get_enterprise_integration_console(_client("enterprise_core"))
    )

    text = repr(payload).lower()
    assert "encrypted_key" not in text
    assert "hashed_key" not in text
    assert "raw_secret" in text
    assert payload["raw_secret_visible"] is False


def test_sandbox_qualification_route_rejects_locked_plan(monkeypatch) -> None:
    monkeypatch.setattr(
        settings_router,
        "_load_raw",
        lambda user_id: {"subscription": {"plan_id": "starter"}},
    )
    body = EnterpriseSandboxQualificationRequest(
        credential_profile_id="enterprise_core_api_reference",
        requested_scope_ids=[_profile_scope_id()],
        provided_input_ids=[],
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            evaluate_enterprise_sandbox_qualification(body, _client("starter"))
        )

    assert exc_info.value.status_code == 403


def test_sandbox_qualification_route_rejects_unknown_identifier(monkeypatch) -> None:
    monkeypatch.setattr(
        settings_router,
        "_load_raw",
        lambda user_id: {"subscription": {"plan_id": "enterprise_core"}},
    )
    body = EnterpriseSandboxQualificationRequest(
        credential_profile_id="enterprise_core_api_reference",
        requested_scope_ids=["unknown:scope"],
        provided_input_ids=[],
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            evaluate_enterprise_sandbox_qualification(body, _client("enterprise_core"))
        )

    assert exc_info.value.status_code == 400


def test_sandbox_qualification_route_is_evaluate_only_and_fail_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        settings_router,
        "_load_raw",
        lambda user_id: {"subscription": {"plan_id": "enterprise_core"}},
    )
    body = EnterpriseSandboxQualificationRequest(
        credential_profile_id="enterprise_core_api_reference",
        requested_scope_ids=[_profile_scope_id()],
        provided_input_ids=list(COMMON_REQUIRED_CUSTOMER_INPUTS),
    )

    payload = asyncio.run(
        evaluate_enterprise_sandbox_qualification(
            body,
            _client("enterprise_core"),
        )
    )

    assert payload["environment"] == "sandbox"
    assert payload["persisted"] is False
    assert payload["missing_input_ids"] == []
    assert payload["security_controls_approved"] == 0
    assert payload["sandbox_ready"] is False
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False
    assert all(
        check["status"] == "blocked_missing_security_controls"
        for check in payload["readiness_checks"]
    )
