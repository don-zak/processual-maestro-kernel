import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from starlette.requests import Request

from processual_api.routers.settings_admin_api_key_provisioning import (
    _require_api_key_provisioning_admin,
    admin_api_key_access_catalog,
    admin_api_key_operational_profiles,
)

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "processual_api" / "static" / "js"
WORKSPACE_SCRIPT = JS / "admin_api_key_provisioning_workspace.js"
EVALUATION_SCRIPT = JS / "admin_evaluation_grants.js"
SESSION_SCRIPT = JS / "admin_session.js"
ROUTERS_INIT = ROOT / "processual_api" / "routers" / "__init__.py"


def _workspace_source() -> str:
    return WORKSPACE_SCRIPT.read_text(encoding="utf-8")


def _evaluation_source() -> str:
    return EVALUATION_SCRIPT.read_text(encoding="utf-8")


def _session_source() -> str:
    return SESSION_SCRIPT.read_text(encoding="utf-8")


def _catalog_test_app() -> FastAPI:
    app = FastAPI()

    @app.get("/health/live")
    async def health_live() -> dict:
        return {"status": "ok"}

    @app.get("/adapters/status")
    async def adapters_status() -> dict:
        return {"status": "ok"}

    @app.post("/cgt/govern")
    async def cgt_govern() -> dict:
        return {"status": "ok"}

    @app.get("/settings/example")
    async def settings_example() -> dict:
        return {"status": "locked"}

    return app


def _request(app: FastAPI | None = None) -> Request:
    request_app = app or FastAPI()
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/settings/admin/api-key-access-catalog",
            "headers": [],
            "app": request_app,
        }
    )


def test_admin_operational_profile_catalog_requires_admin_authority() -> None:
    _require_api_key_provisioning_admin({"role": "security_admin", "scopes": []})
    _require_api_key_provisioning_admin({"role": "client", "scopes": ["admin:api_keys:read"]})

    with pytest.raises(HTTPException) as exc_info:
        _require_api_key_provisioning_admin({"role": "client", "scopes": ["read:health"]})

    assert exc_info.value.status_code == 403


def test_admin_operational_profile_catalog_is_safe_and_non_production() -> None:
    payload = asyncio.run(
        admin_api_key_operational_profiles(
            {"role": "security_admin", "scopes": ["admin:api_keys:write"]}
        )
    )

    assert payload["admin_provisioning_catalog"] is True
    assert payload["raw_secret_visible"] is False
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False
    assert payload["profiles"]
    for profile in payload["profiles"]:
        assert profile["production_allowed"] is False
        assert profile["runtime_connector_approved"] is False
        assert "allowed_scopes" in profile
        assert "forbidden_scopes" in profile


def test_admin_access_catalog_is_fail_closed_and_policy_driven() -> None:
    catalog_app = _catalog_test_app()
    payload = asyncio.run(
        admin_api_key_access_catalog(
            _request(catalog_app),
            {"role": "security_admin", "scopes": ["admin:api_keys:write"]},
        )
    )

    by_key = {
        (endpoint["method"], endpoint["path"]): endpoint
        for endpoint in payload["endpoints"]
    }
    assert by_key[("GET", "/health/live")]["grantable"] is True
    assert by_key[("GET", "/adapters/status")]["grantable"] is True
    assert by_key[("POST", "/cgt/govern")]["grantable"] is True
    assert by_key[("GET", "/settings/example")]["grantable"] is False
    assert not any(
        str(scope).startswith("admin:")
        for endpoint in payload["endpoints"]
        if endpoint["grantable"]
        for scope in endpoint["required_scopes"]
    )


def test_provisioning_workspace_uses_fixed_external_evaluation_slot() -> None:
    source = _workspace_source()

    required = [
        "const WORKSPACE_ID = 'admin-api-key-external-provisioning-slot'",
        "Operational Profile",
        "Eligible Endpoints",
        "Derived Runtime Scopes",
        "Backend Route Inventory",
        "Access Preview",
        "/settings/admin/api-key-operational-profiles",
        "/settings/admin/api-key-access-catalog",
        "data-api-key-access-endpoint",
    ]
    for marker in required:
        assert marker in source

    assert "admin-api-key-provisioning-mode" not in source
    assert "appendChild(workspace)" not in source
    assert "before(workspace)" not in source
    assert "insertBefore" not in source


def test_endpoint_selection_derives_scopes_but_profile_is_intent_only() -> None:
    source = _workspace_source()

    assert "Choosing a profile does not mutate runtime scopes" in source
    assert "selectedEndpointScopes" in source
    assert "syncScopesFromEndpointSelection" in source
    assert "derivedScopes.join('\\n')" in source
    assert "profile.allowed_scopes" in source
    assert "target.value = profile" not in source
    assert "target.value = allowed.join" not in source


def test_external_evaluation_grant_receives_selected_endpoint_scopes() -> None:
    source = _evaluation_source()

    assert "function selectedEvaluationScopes()" in source
    assert "PMK_ADMIN_API_KEY_PROVISIONING_WORKSPACE" in source
    assert "workspace.selectedScopes()" in source

    create_start = source.index("async function createEvaluationGrant()")
    issue_start = source.index("async function issueEvaluationKey", create_start)
    create_source = source[create_start:issue_start]
    assert "const readiness = updateEvaluationReadiness();" in create_source
    assert "if (!readiness.ready)" in create_source
    assert "const allowedScopes = readiness.scopes;" in create_source
    assert "...(allowedScopes.length ? { allowed_scopes: allowedScopes } : {})" in create_source


def test_workspace_does_not_store_secrets_or_observe_dom_forever() -> None:
    source = _workspace_source()

    assert "sessionStorage.setItem" not in source
    assert "localStorage.setItem" not in source
    assert "MutationObserver" not in source
    assert "while (" not in source
    assert "const MAX_INIT_ATTEMPTS = 30" in source
    assert "initAttempts < MAX_INIT_ATTEMPTS" in source


def test_workspace_script_loads_only_after_verified_admin_session() -> None:
    source = _session_source()

    required = [
        "API_KEY_WORKSPACE_SCRIPT_SELECTOR",
        "admin_api_key_provisioning_workspace.js?v=adminapikeyworkspace03-single-owner",
        "function loadApiKeyProvisioningWorkspace()",
        "script.dataset.adminApiKeyProvisioningWorkspace = 'true'",
        "document.body.dataset.adminSession = 'ok'",
        "loadApiKeyProvisioningWorkspace();",
    ]
    for marker in required:
        assert marker in source

    assert source.index("document.body.dataset.adminSession = 'ok'") < source.index(
        "loadApiKeyProvisioningWorkspace();"
    )


def test_admin_provisioning_route_extension_is_registered() -> None:
    source = ROUTERS_INIT.read_text(encoding="utf-8")
    assert "settings_admin_api_key_provisioning" in source
